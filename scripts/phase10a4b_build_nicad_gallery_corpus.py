#!/usr/bin/env python3

import csv
import json
import re
import shutil
import subprocess
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GALLERY_MAP = ROOT / "results" / "phase10a5_gallery_private_mapping.csv"
PARENT_MAP = ROOT / "results" / "phase10a5_parent_private_mapping.csv"

CACHE = ROOT / "data" / "phase10a4b_gallery_git_cache"
OUT_CORPUS = ROOT / "data" / "phase10a4b_nicad_gallery_corpus"

OUT_MAP = ROOT / "results" / "phase10a4b_gallery_class_to_java_mapping.csv"
OUT_REPO = ROOT / "results" / "phase10a4b_gallery_repository_snapshot_audit.csv"
OUT_SUMMARY = ROOT / "results" / "phase10a4b_gallery_summary.json"

UA = "mod-provenance-research/phase10a4b"


def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run(cmd, cwd=None, capture=False, check=True):
    env = dict(__import__("os").environ)
    # Never allow git to stop the automated benchmark for credentials.
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"

    if capture:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            env=env
        )
        return p.stdout.strip()

    subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        env=env
    )
    return ""


def api_json(url, retries=4):
    req = urllib.request.Request(url, headers={"User-Agent": UA})

    for n in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if n + 1 == retries:
                raise
            time.sleep(2 ** n)


def normalize_repo_url(url):
    if not url:
        return ""

    url = url.strip().rstrip("/")

    # GitHub repository URL only
    m = re.match(
        r"https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)",
        url,
        flags=re.I
    )
    if not m:
        return ""

    owner, repo = m.groups()
    repo = repo.removesuffix(".git")

    return f"https://github.com/{owner}/{repo}"


def normalize_version(v):
    v = (v or "").strip().lower()

    v = re.sub(r"^refs/tags/", "", v)
    v = re.sub(r"^[vV]", "", v)

    # common separators
    v = re.sub(r"[-_+\.]", "", v)

    # characters often irrelevant for tag normalization
    v = re.sub(r"[^a-z0-9]", "", v)

    return v


def clone_or_update(repo_url):
    key = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
    owner = repo_url.rstrip("/").split("/")[-2]
    dst = CACHE / f"{owner}__{key}"

    CACHE.mkdir(parents=True, exist_ok=True)

    if not (dst / ".git").exists():
        if dst.exists():
            shutil.rmtree(dst)

        print(f"[clone] {repo_url}")

        run([
            "git", "clone",
            "--filter=blob:none",
            "--no-checkout",
            repo_url,
            str(dst)
        ])
    else:
        print(f"[cache] {repo_url}")

    # Ensure refs/tags/history are usable.
    run([
        "git", "fetch",
        "--force",
        "--tags",
        "origin",
        "+refs/heads/*:refs/remotes/origin/*"
    ], cwd=dst, check=False)

    return dst


def find_exact_tag(repo, version_number):
    nv = normalize_version(version_number)
    if not nv:
        return None

    tags = run(
        ["git", "tag", "--list"],
        cwd=repo,
        capture=True,
        check=False
    ).splitlines()

    matches = []

    for tag in tags:
        if normalize_version(tag) == nv:
            matches.append(tag)

    if not matches:
        return None

    # deterministic
    matches.sort(key=lambda x: (len(x), x))
    return matches[0]


def resolve_snapshot(repo, version_number, date_published):
    tag = find_exact_tag(repo, version_number)

    if tag:
        commit = run(
            ["git", "rev-list", "-n", "1", tag],
            cwd=repo,
            capture=True
        )
        if commit:
            return {
                "snapshot_commit": commit,
                "snapshot_ref": tag,
                "snapshot_resolution": "EXACT_NORMALIZED_TAG",
                "snapshot_exact_release_claim": True,
            }

    # Same conservative policy as Phase10A3:
    # nearest repository commit at/before release date.
    if date_published:
        commit = run([
            "git", "rev-list",
            "-n", "1",
            f"--before={date_published}",
            "--all"
        ], cwd=repo, capture=True, check=False)

        if commit:
            return {
                "snapshot_commit": commit,
                "snapshot_ref": "",
                "snapshot_resolution": "DATE_HEURISTIC",
                "snapshot_exact_release_claim": False,
            }

    return {
        "snapshot_commit": "",
        "snapshot_ref": "",
        "snapshot_resolution": "NO_COMMIT_RESOLVED",
        "snapshot_exact_release_claim": False,
    }


def checkout(repo, commit):
    run(["git", "checkout", "--detach", "--force", commit], cwd=repo)


def java_files(repo):
    out = []

    for p in repo.rglob("*.java"):
        # ignore git internals, build/cache output
        rel = p.relative_to(repo).as_posix()

        lower = rel.lower()

        if "/build/" in f"/{lower}/":
            continue
        if "/.gradle/" in f"/{lower}/":
            continue
        if "/target/" in f"/{lower}/":
            continue
        if "/out/" in f"/{lower}/":
            continue
        if "/generated/" in f"/{lower}/":
            continue

        out.append(rel)

    return out


def class_to_expected_java_path(class_rel):
    p = class_rel.replace("\\", "/")

    if not p.endswith(".class"):
        return ""

    p = p[:-6]

    # Inner class belongs to outer source.
    base = p.rsplit("/", 1)[-1]
    outer = base.split("$", 1)[0]

    prefix = p.rsplit("/", 1)[0] if "/" in p else ""

    return f"{prefix}/{outer}.java" if prefix else f"{outer}.java"


def build_java_indexes(files):
    suffix = defaultdict(list)
    basename = defaultdict(list)

    for rel in files:
        base = Path(rel).name
        basename[base].append(rel)

        # all package-like suffixes
        parts = rel.split("/")
        for i in range(len(parts)):
            suffix["/".join(parts[i:])].append(rel)

    return suffix, basename


def map_class(class_rel, suffix_index, basename_index):
    expected = class_to_expected_java_path(class_rel)

    if expected:
        exact_suffix = suffix_index.get(expected, [])

        if len(exact_suffix) == 1:
            return (
                exact_suffix[0],
                "EXACT_PACKAGE_SUFFIX",
                1
            )

        if len(exact_suffix) > 1:
            return (
                "",
                "AMBIGUOUS_PACKAGE_SUFFIX",
                len(exact_suffix)
            )

    basename = Path(expected).name if expected else ""

    candidates = basename_index.get(basename, [])

    if len(candidates) == 1:
        return (
            candidates[0],
            "UNIQUE_BASENAME",
            1
        )

    if len(candidates) > 1:
        return (
            "",
            "AMBIGUOUS_BASENAME",
            len(candidates)
        )

    return (
        "",
        "NO_BASENAME_MATCH",
        0
    )


def get_project_source_url(project_id):
    project = api_json(
        f"https://api.modrinth.com/v2/project/{project_id}"
    )

    candidates = [
        project.get("source_url"),
        project.get("issues_url"),
        project.get("wiki_url"),
    ]

    for url in candidates:
        repo = normalize_repo_url(url)
        if repo:
            return repo

    return ""


def get_version(version_id):
    return api_json(
        f"https://api.modrinth.com/v2/version/{version_id}"
    )


def main():
    gallery = load_csv(GALLERY_MAP)
    parents = load_csv(PARENT_MAP)

    if len(gallery) != 10448:
        raise RuntimeError(
            f"Expected 10448 gallery CODE rows, got {len(gallery)}"
        )

    parent_by_anon = {
        r["anonymous_parent_id"]: r
        for r in parents
    }

    grouped = defaultdict(list)

    for row in gallery:
        grouped[row["anonymous_parent_id"]].append(row)

    # Frozen parent universe contains 60 projects, but only parents
    # with at least one filtered CODE component appear in the gallery
    # component mapping. Phase10A5 audit shows 55 CODE-bearing parents.
    parent_universe_count = len(parents)

    if parent_universe_count != 60:
        raise RuntimeError(
            f"Expected 60 frozen gallery parents, got {parent_universe_count}"
        )

    if len(grouped) != 55:
        raise RuntimeError(
            f"Expected 55 CODE-bearing gallery parents, got {len(grouped)}"
        )

    if OUT_CORPUS.exists():
        shutil.rmtree(OUT_CORPUS)

    OUT_CORPUS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    mapping_rows = []
    repo_rows = []

    for idx, anon_parent in enumerate(sorted(grouped), 1):
        rows = grouped[anon_parent]

        first = rows[0]

        project_id = first["project_id"]
        fresh_id = first["fresh_id"]
        version_id = first["version_id"]
        version_number = first["version_number"]
        frozen_split = first["frozen_split"]

        print()
        print(
            f"[{idx}/60] {anon_parent} "
            f"{fresh_id} version={version_number}"
        )

        repo_url = ""
        snapshot_commit = ""
        snapshot_ref = ""
        snapshot_resolution = ""
        exact_claim = False
        error = ""

        try:
            version = get_version(version_id)
            date_published = version.get("date_published", "")

            repo_url = get_project_source_url(project_id)

            if not repo_url:
                snapshot_resolution = "NO_GITHUB_REPOSITORY"
                error = "No GitHub repository in Modrinth project metadata"

                for r in rows:
                    mapping_rows.append({
                        **r,
                        "github_repo": "",
                        "date_published": date_published,
                        "snapshot_commit": "",
                        "snapshot_ref": "",
                        "snapshot_resolution": snapshot_resolution,
                        "snapshot_exact_release_claim": False,
                        "java_path": "",
                        "java_mapping_status": "NO_REPOSITORY",
                        "java_candidate_count": 0,
                        "source_resolvable": False,
                        "high_confidence_mapping": False,
                        "nicad_gallery_relpath": "",
                    })

                repo_rows.append({
                    "anonymous_parent_id": anon_parent,
                    "fresh_id": fresh_id,
                    "project_id": project_id,
                    "frozen_split": frozen_split,
                    "version_id": version_id,
                    "version_number": version_number,
                    "date_published": date_published,
                    "github_repo": "",
                    "snapshot_commit": "",
                    "snapshot_ref": "",
                    "snapshot_resolution": snapshot_resolution,
                    "snapshot_exact_release_claim": False,
                    "error": error,
                })

                continue

            checkout_dir = clone_or_update(repo_url)

            res = resolve_snapshot(
                checkout_dir,
                version_number,
                date_published
            )

            snapshot_commit = res["snapshot_commit"]
            snapshot_ref = res["snapshot_ref"]
            snapshot_resolution = res["snapshot_resolution"]
            exact_claim = res["snapshot_exact_release_claim"]

            if not snapshot_commit:
                raise RuntimeError("No snapshot commit resolved")

            checkout(checkout_dir, snapshot_commit)

            files = java_files(checkout_dir)

            suffix_index, basename_index = build_java_indexes(files)

            # Each unique Java source is materialized only once per parent.
            # Multiple class files such as Outer$Inner.class may map to it.
            copied = {}

            for r in rows:
                java_path, status, count = map_class(
                    r["relative_path"],
                    suffix_index,
                    basename_index
                )

                source_resolvable = bool(java_path)

                high_conf = (
                    source_resolvable
                    and snapshot_resolution == "EXACT_NORMALIZED_TAG"
                    and status in {
                        "EXACT_PACKAGE_SUFFIX",
                        "UNIQUE_BASENAME"
                    }
                )

                relout = ""

                if source_resolvable:
                    if java_path not in copied:
                        src = checkout_dir / java_path

                        # identity-neutral NiCad folder names
                        number = len(copied) + 1
                        filename = f"{anon_parent}_S{number:06d}.java"

                        dst = (
                            OUT_CORPUS
                            / anon_parent
                            / filename
                        )

                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)

                        copied[java_path] = dst

                    dst = copied[java_path]

                    relout = (
                        dst.relative_to(ROOT)
                        .as_posix()
                    )

                mapping_rows.append({
                    **r,
                    "github_repo": repo_url,
                    "date_published": date_published,
                    "snapshot_commit": snapshot_commit,
                    "snapshot_ref": snapshot_ref,
                    "snapshot_resolution": snapshot_resolution,
                    "snapshot_exact_release_claim": exact_claim,
                    "java_path": java_path,
                    "java_mapping_status": status,
                    "java_candidate_count": count,
                    "source_resolvable": source_resolvable,
                    "high_confidence_mapping": high_conf,
                    "nicad_gallery_relpath": relout,
                })

            repo_rows.append({
                "anonymous_parent_id": anon_parent,
                "fresh_id": fresh_id,
                "project_id": project_id,
                "frozen_split": frozen_split,
                "version_id": version_id,
                "version_number": version_number,
                "date_published": date_published,
                "github_repo": repo_url,
                "snapshot_commit": snapshot_commit,
                "snapshot_ref": snapshot_ref,
                "snapshot_resolution": snapshot_resolution,
                "snapshot_exact_release_claim": exact_claim,
                "error": "",
            })

        except Exception as ex:
            error = repr(ex)
            print("ERROR:", error)

            repo_rows.append({
                "anonymous_parent_id": anon_parent,
                "fresh_id": fresh_id,
                "project_id": project_id,
                "frozen_split": frozen_split,
                "version_id": version_id,
                "version_number": version_number,
                "date_published": "",
                "github_repo": repo_url,
                "snapshot_commit": snapshot_commit,
                "snapshot_ref": snapshot_ref,
                "snapshot_resolution": (
                    snapshot_resolution or "REPOSITORY_ERROR"
                ),
                "snapshot_exact_release_claim": exact_claim,
                "error": error,
            })

            # Preserve one row per original gallery component.
            existing_names = {
                x["anonymous_filename"]
                for x in mapping_rows
                if x["anonymous_parent_id"] == anon_parent
            }

            for r in rows:
                if r["anonymous_filename"] in existing_names:
                    continue

                mapping_rows.append({
                    **r,
                    "github_repo": repo_url,
                    "date_published": "",
                    "snapshot_commit": snapshot_commit,
                    "snapshot_ref": snapshot_ref,
                    "snapshot_resolution": (
                        snapshot_resolution or "REPOSITORY_ERROR"
                    ),
                    "snapshot_exact_release_claim": exact_claim,
                    "java_path": "",
                    "java_mapping_status": "REPOSITORY_ERROR",
                    "java_candidate_count": 0,
                    "source_resolvable": False,
                    "high_confidence_mapping": False,
                    "nicad_gallery_relpath": "",
                })

    # Mapping output
    mapping_fields = list(gallery[0].keys()) + [
        "github_repo",
        "date_published",
        "snapshot_commit",
        "snapshot_ref",
        "snapshot_resolution",
        "snapshot_exact_release_claim",
        "java_path",
        "java_mapping_status",
        "java_candidate_count",
        "source_resolvable",
        "high_confidence_mapping",
        "nicad_gallery_relpath",
    ]

    with OUT_MAP.open(
        "w", encoding="utf-8", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=mapping_fields)
        w.writeheader()
        w.writerows(mapping_rows)

    repo_fields = [
        "anonymous_parent_id",
        "fresh_id",
        "project_id",
        "frozen_split",
        "version_id",
        "version_number",
        "date_published",
        "github_repo",
        "snapshot_commit",
        "snapshot_ref",
        "snapshot_resolution",
        "snapshot_exact_release_claim",
        "error",
    ]

    with OUT_REPO.open(
        "w", encoding="utf-8", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=repo_fields)
        w.writeheader()
        w.writerows(repo_rows)

    mapping_status = Counter(
        r["java_mapping_status"]
        for r in mapping_rows
    )

    snapshot_status = Counter(
        r["snapshot_resolution"]
        for r in repo_rows
    )

    resolvable = [
        r for r in mapping_rows
        if str(r["source_resolvable"]).lower() == "true"
    ]

    high_conf = [
        r for r in mapping_rows
        if str(r["high_confidence_mapping"]).lower() == "true"
    ]

    unique_materialized = {
        r["nicad_gallery_relpath"]
        for r in resolvable
        if r["nicad_gallery_relpath"]
    }

    parent_resolvable_counts = Counter(
        r["anonymous_parent_id"]
        for r in resolvable
    )

    summary = {
        "phase10a4b_complete": True,
        "scope": "NICAD_FROZEN_GALLERY_SOURCE_MAPPING",
        "frozen_gallery_parent_universe": 60,
        "code_bearing_gallery_projects": len(grouped),
        "zero_code_gallery_projects": 60 - len(grouped),
        "input_gallery_projects": len(grouped),
        "input_gallery_code_components": len(gallery),
        "repository_snapshot_resolution_counts":
            dict(snapshot_status),
        "java_mapping_status_counts":
            dict(mapping_status),
        "source_resolvable_gallery_components":
            len(resolvable),
        "source_resolvable_gallery_component_rate":
            len(resolvable) / len(gallery),
        "high_confidence_gallery_components":
            len(high_conf),
        "materialized_unique_java_files":
            len(unique_materialized),
        "gallery_parents_with_any_resolvable_source":
            len(parent_resolvable_counts),
        "code_bearing_gallery_parents_without_resolvable_source":
            len(grouped) - len(parent_resolvable_counts),
        "frozen_parents_with_zero_code_components":
            60 - len(grouped),
        "repository_errors":
            sum(bool(r["error"]) for r in repo_rows),
        "manual_annotation_used": False,
        "important_interpretation": {
            "exact_normalized_tag":
                "Frozen Modrinth version number matched a Git tag after normalization.",
            "date_heuristic":
                "Nearest repository commit at or before frozen Modrinth release date; not claimed as exact build source.",
            "mapping_unit":
                "CLASS entry to Java source; inner classes collapse to their outer Java source.",
            "nicad_materialization":
                "Each unique Java source is materialized once per frozen parent."
        }
    }

    OUT_SUMMARY.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("=== PHASE10A4B SUMMARY ===")
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
