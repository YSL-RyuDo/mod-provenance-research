#!/usr/bin/env python3

import csv
import json
import shutil
import subprocess
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

MAPPING = ROOT / "results" / "phase10a3_class_to_java_mapping.csv"
STONE_QUERY = ROOT / "results" / "phase10a5_query_private_mapping.csv"

OUT_ROOT = ROOT / "data" / "phase10a4_nicad_query_corpus"
CACHE_ROOT = ROOT / "data" / "phase10a4_git_cache"

OUT_MAP = ROOT / "results" / "phase10a4_nicad_query_mapping.csv"
OUT_SUMMARY = ROOT / "results" / "phase10a4_nicad_query_summary.json"


def run(cmd, cwd=None):
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def truthy(v):
    return str(v).strip().lower() in {"true", "1", "yes"}


def safe_repo_name(url):
    return url.rstrip("/").split("/")[-1].removesuffix(".git")


def ensure_snapshot(repo_url, commit):
    key = f"{safe_repo_name(repo_url)}_{commit[:12]}"
    dst = CACHE_ROOT / key

    if dst.exists() and (dst / ".git").exists():
        return dst

    if dst.exists():
        shutil.rmtree(dst)

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    run([
        "git", "clone",
        "--filter=blob:none",
        "--no-checkout",
        repo_url,
        str(dst)
    ])

    run(["git", "fetch", "--depth", "1", "origin", commit], cwd=dst)
    run(["git", "checkout", "--detach", commit], cwd=dst)

    return dst


def main():
    rows = load_csv(MAPPING)
    qmap_rows = load_csv(STONE_QUERY)

    anon_by_node = {
        r["node_id"]: (r["anonymous_query_id"], r["anonymous_filename"])
        for r in qmap_rows
    }

    selected = [
        r for r in rows
        if truthy(r["source_resolvable"])
    ]

    if len(selected) != 1169:
        raise RuntimeError(
            f"Expected 1169 source-resolvable components, got {len(selected)}"
        )

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)

    OUT_ROOT.mkdir(parents=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    output_rows = []
    failures = []

    snapshot_cache = {}

    for i, r in enumerate(selected, 1):
        node_id = r["node_id"]

        if node_id not in anon_by_node:
            failures.append({
                "node_id": node_id,
                "reason": "NO_PHASE10A5_ANONYMOUS_QUERY_MAPPING"
            })
            continue

        anon_qid, anon_filename = anon_by_node[node_id]

        repo = r["github_repo"]
        commit = r["snapshot_commit"]
        java_path = r["java_path"]

        if not repo or not commit or not java_path:
            failures.append({
                "node_id": node_id,
                "reason": "MISSING_REPO_COMMIT_OR_JAVA_PATH"
            })
            continue

        cache_key = (repo, commit)

        try:
            if cache_key not in snapshot_cache:
                snapshot_cache[cache_key] = ensure_snapshot(repo, commit)

            checkout = snapshot_cache[cache_key]
            src = checkout / java_path

            if not src.is_file():
                failures.append({
                    "node_id": node_id,
                    "reason": "JAVA_FILE_MISSING_AFTER_CHECKOUT",
                    "repo": repo,
                    "commit": commit,
                    "java_path": java_path
                })
                continue

            # one query component = one isolated source system fragment
            qdir = OUT_ROOT / anon_qid / anon_filename.removesuffix(".class")
            qdir.mkdir(parents=True, exist_ok=True)

            dst = qdir / "Query.java"
            shutil.copy2(src, dst)

            output_rows.append({
                "anonymous_query_id": anon_qid,
                "anonymous_filename": anon_filename,
                "query_id": r["query_id"],
                "node_id": node_id,
                "source_fresh_id": r["source_fresh_id"],
                "source_version_id": r["source_version_id"],
                "ground_truth_repo": repo,
                "snapshot_commit": commit,
                "snapshot_resolution": r["snapshot_resolution"],
                "java_path": java_path,
                "java_mapping_status": r["java_mapping_status"],
                "high_confidence_mapping": r["high_confidence_mapping"],
                "nicad_source_relpath": str(
                    dst.relative_to(ROOT)
                ).replace("\\", "/"),
            })

            if i % 50 == 0:
                print(f"[{i}/{len(selected)}] copied")

        except Exception as e:
            failures.append({
                "node_id": node_id,
                "reason": "EXCEPTION",
                "error": repr(e),
                "repo": repo,
                "commit": commit
            })

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "anonymous_query_id",
        "anonymous_filename",
        "query_id",
        "node_id",
        "source_fresh_id",
        "source_version_id",
        "ground_truth_repo",
        "snapshot_commit",
        "snapshot_resolution",
        "java_path",
        "java_mapping_status",
        "high_confidence_mapping",
        "nicad_source_relpath",
    ]

    with OUT_MAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(output_rows)

    resolution_counts = Counter(
        r["snapshot_resolution"] for r in output_rows
    )

    summary = {
        "phase10a4_query_corpus_complete":
            len(output_rows) == len(selected),
        "expected_source_resolvable": 1169,
        "materialized_source_components": len(output_rows),
        "failures": len(failures),
        "unique_query_ids": len({
            r["anonymous_query_id"] for r in output_rows
        }),
        "unique_snapshots": len(snapshot_cache),
        "snapshot_resolution_counts": dict(resolution_counts),
        "high_confidence_components": sum(
            truthy(r["high_confidence_mapping"])
            for r in output_rows
        ),
        "manual_annotation_used": False,
        "failure_examples": failures[:20],
    }

    OUT_SUMMARY.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
