import hashlib
import json
import os
import shutil
import statistics
import subprocess
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

INPUT_CSV = Path(
    "results/phase6a_fresh_corpus.csv"
)

DATA_ROOT = Path(
    "data/fresh_corpus"
)

CURRENT_ROOT = (
    DATA_ROOT
    / "jars/current"
)

HISTORICAL_ROOT = (
    DATA_ROOT
    / "jars/historical"
)

REGISTRY_ROOT = Path(
    "data/fresh_registry"
)

RESULT_ROOT = Path(
    "results"
)


for directory in [
    CURRENT_ROOT,
    HISTORICAL_ROOT,
    REGISTRY_ROOT,
    RESULT_ROOT,
]:

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


CURRENT_PACKAGE_CSV = (
    REGISTRY_ROOT
    / "fresh_current_package_registry.csv"
)

HISTORICAL_PACKAGE_CSV = (
    REGISTRY_ROOT
    / "fresh_historical_package_registry.csv"
)

CURRENT_COMPONENT_CSV = (
    REGISTRY_ROOT
    / "fresh_current_component_registry.csv"
)

HISTORICAL_COMPONENT_CSV = (
    REGISTRY_ROOT
    / "fresh_historical_component_registry.csv"
)

DUPLICATE_CSV = (
    RESULT_ROOT
    / "phase6b_current_cross_project_duplicates.csv"
)

FAILURE_JSON = (
    RESULT_ROOT
    / "phase6b_failures.json"
)

SUMMARY_JSON = (
    RESULT_ROOT
    / "phase6b_summary.json"
)


STRUCTURED_SUFFIXES = {
    ".json",
    ".json5",
    ".toml",
    ".yaml",
    ".yml",
    ".xml",
    ".properties",
    ".cfg",
    ".conf",
    ".mcmeta",
}

IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


# =========================================================
# Curl
# =========================================================

CURL_EXECUTABLE = (
    shutil.which("curl.exe")
    or
    shutil.which("curl")
)


if CURL_EXECUTABLE is None:

    raise RuntimeError(
        "curl.exe를 찾을 수 없습니다. "
        "Windows 기본 curl 설치 상태를 확인하세요."
    )


print(
    "curl executable:",
    CURL_EXECUTABLE
)


# =========================================================
# Value helpers
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:
        pass

    return str(
        value
    ).strip()


def json_list(value):

    if value is None:
        return []

    try:

        if pd.isna(value):
            return []

    except Exception:
        pass


    if isinstance(
        value,
        list
    ):

        return value


    text = str(
        value
    ).strip()


    if not text:
        return []


    try:

        parsed = json.loads(
            text
        )

        if isinstance(
            parsed,
            list
        ):

            return parsed

    except Exception:
        pass


    return []


# =========================================================
# File hashing
# =========================================================

def file_hash(
    path,
    algorithm,
    chunk_size=1024 * 1024,
):

    digest = hashlib.new(
        algorithm
    )


    with open(
        path,
        "rb"
    ) as f:

        while True:

            chunk = f.read(
                chunk_size
            )

            if not chunk:
                break

            digest.update(
                chunk
            )


    return (
        digest.hexdigest()
    )


def verify_expected_hash(
    path,
    sha1="",
    sha512="",
):

    sha1 = (
        clean_text(
            sha1
        ).lower()
    )

    sha512 = (
        clean_text(
            sha512
        ).lower()
    )


    # Prefer SHA-512 when available.
    if sha512:

        actual = file_hash(
            path,
            "sha512"
        )

        return (
            actual.lower()
            == sha512
        )


    if sha1:

        actual = file_hash(
            path,
            "sha1"
        )

        return (
            actual.lower()
            == sha1
        )


    # Metadata hash unavailable.
    return True


# =========================================================
# Robust resumable downloader
# =========================================================

def download_file(
    url,
    destination,
    expected_sha1="",
    expected_sha512="",
    retries=5,
):

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    # -----------------------------------------------------
    # Existing file
    # -----------------------------------------------------

    if destination.exists():

        print(
            "    checking existing file..."
        )

        try:

            valid = (
                verify_expected_hash(
                    destination,
                    expected_sha1,
                    expected_sha512,
                )
            )

        except Exception as exc:

            print(
                "    existing hash check error:",
                repr(exc)
            )

            valid = False


        if valid:

            print(
                "    existing file valid"
            )

            return {
                "ok":
                    True,

                "status":
                    "EXISTING_VALID",

                "bytes":
                    destination
                    .stat()
                    .st_size,

                "sha256":
                    file_hash(
                        destination,
                        "sha256"
                    ),
            }


        print(
            "    existing file invalid; deleting"
        )

        try:

            destination.unlink()

        except Exception:
            pass


    tmp_path = (
        destination.with_suffix(
            destination.suffix
            + ".part"
        )
    )


    # -----------------------------------------------------
    # Download attempts
    # -----------------------------------------------------

    for attempt in range(
        1,
        retries + 1
    ):

        print(
            f"    download attempt "
            f"{attempt}/{retries}"
        )

        print(
            "    URL:",
            url
        )


        if tmp_path.exists():

            try:

                tmp_path.unlink()

            except Exception:
                pass


        command = [
            CURL_EXECUTABLE,

            # Follow CDN redirects.
            "-L",

            # HTTP 4xx/5xx -> failure.
            "--fail",

            # Show transfer progress.
            "--progress-bar",

            # Connection establishment timeout.
            "--connect-timeout",
            "15",

            # One curl invocation can run at most 5 min.
            "--max-time",
            "300",

            # Abort if transfer stays below
            # 1 KiB/s for 20 seconds.
            "--speed-limit",
            "1024",

            "--speed-time",
            "20",

            # Curl-level retry.
            "--retry",
            "2",

            "--retry-delay",
            "2",

            "--retry-all-errors",

            # Output file.
            "--output",
            str(
                tmp_path
            ),

            url,
        ]


        try:

            process = subprocess.run(
                command,
                check=False,
            )

        except KeyboardInterrupt:

            print()
            print(
                "    interrupted by user"
            )

            if tmp_path.exists():

                try:

                    tmp_path.unlink()

                except Exception:
                    pass

            raise


        except Exception as exc:

            print(
                "    curl execution error:",
                repr(exc)
            )

            process = None


        # -------------------------------------------------
        # Curl failed
        # -------------------------------------------------

        if (
            process is None
            or
            process.returncode != 0
        ):

            code = (
                None
                if process is None
                else process.returncode
            )

            print(
                "    curl failed/stalled."
            )

            print(
                "    return code:",
                code
            )


            if tmp_path.exists():

                try:

                    tmp_path.unlink()

                except Exception:
                    pass


            if attempt < retries:

                wait = (
                    2.0
                    * attempt
                )

                print(
                    f"    retry after "
                    f"{wait:.1f}s"
                )

                time.sleep(
                    wait
                )

                continue


            return {
                "ok":
                    False,

                "status":
                    "DOWNLOAD_FAILED",

                "error":
                    (
                        "curl failed after "
                        f"{retries} attempts; "
                        f"last return code={code}"
                    ),
            }


        # -------------------------------------------------
        # Missing temp file
        # -------------------------------------------------

        if not tmp_path.exists():

            print(
                "    curl finished but "
                "temporary file is missing"
            )


            if attempt < retries:

                time.sleep(
                    2.0
                    * attempt
                )

                continue


            return {
                "ok":
                    False,

                "status":
                    "DOWNLOAD_FAILED",

                "error":
                    "temporary file missing",
            }


        file_size_mb = (
            tmp_path.stat().st_size
            / 1024
            / 1024
        )


        print(
            "    downloaded:",
            f"{file_size_mb:.2f} MB"
        )


        # -------------------------------------------------
        # Verify digest
        # -------------------------------------------------

        print(
            "    verifying expected hash..."
        )


        try:

            valid = (
                verify_expected_hash(
                    tmp_path,
                    expected_sha1,
                    expected_sha512,
                )
            )

        except Exception as exc:

            print(
                "    hash verification error:",
                repr(exc)
            )

            valid = False


        if not valid:

            print(
                "    HASH MISMATCH"
            )


            try:

                tmp_path.unlink()

            except Exception:
                pass


            if attempt < retries:

                time.sleep(
                    2.0
                    * attempt
                )

                continue


            return {
                "ok":
                    False,

                "status":
                    "DOWNLOAD_FAILED",

                "error":
                    "expected hash mismatch",
            }


        print(
            "    expected hash OK"
        )


        # -------------------------------------------------
        # Finalize
        # -------------------------------------------------

        os.replace(
            tmp_path,
            destination
        )


        print(
            "    calculating SHA-256..."
        )


        sha256 = file_hash(
            destination,
            "sha256"
        )


        print(
            "    download complete"
        )


        return {
            "ok":
                True,

            "status":
                "DOWNLOADED",

            "bytes":
                destination
                .stat()
                .st_size,

            "sha256":
                sha256,
        }


    return {
        "ok":
            False,

        "status":
            "DOWNLOAD_FAILED",

        "error":
            "unexpected downloader termination",
    }


# =========================================================
# Component classification
# =========================================================

def classify_component(
    relative_path
):

    normalized = (
        relative_path
        .replace(
            "\\",
            "/"
        )
    )

    lower = (
        normalized.lower()
    )


    # META-INF is excluded from provenance components.
    if lower.startswith(
        "meta-inf/"
    ):

        return None


    if lower.endswith(
        ".class"
    ):

        return (
            "CODE_BINARY"
        )


    suffix = (
        Path(
            lower
        ).suffix
    )


    if suffix in (
        STRUCTURED_SUFFIXES
    ):

        return (
            "STRUCTURED"
        )


    if suffix in (
        IMAGE_SUFFIXES
    ):

        return (
            "IMAGE"
        )


    return None


# =========================================================
# ZIP component hashing
# =========================================================

def zip_entry_sha256(
    jar,
    info,
    chunk_size=1024 * 1024,
):

    digest = (
        hashlib.sha256()
    )


    with jar.open(
        info,
        "r"
    ) as f:

        while True:

            chunk = f.read(
                chunk_size
            )

            if not chunk:
                break

            digest.update(
                chunk
            )


    return (
        digest.hexdigest()
    )


# =========================================================
# Scan JAR
# =========================================================

def scan_jar(
    jar_path,
    project_meta,
    release_kind,
    version_id,
    version_number,
):

    rows = []

    counts = defaultdict(
        int
    )


    print(
        "    scanning JAR:",
        jar_path.name
    )


    with zipfile.ZipFile(
        jar_path,
        "r"
    ) as jar:

        infos = (
            jar.infolist()
        )

        total_entries = len(
            infos
        )


        for entry_index, info in (
            enumerate(
                infos,
                start=1
            )
        ):

            if info.is_dir():
                continue


            relative_path = (
                info.filename
                .replace(
                    "\\",
                    "/"
                )
            )


            modality = (
                classify_component(
                    relative_path
                )
            )


            if modality is None:
                continue


            digest = (
                zip_entry_sha256(
                    jar,
                    info
                )
            )


            rows.append({
                "fresh_id":
                    project_meta[
                        "fresh_id"
                    ],

                "project_id":
                    project_meta[
                        "project_id"
                    ],

                "slug":
                    project_meta[
                        "slug"
                    ],

                "title":
                    project_meta[
                        "title"
                    ],

                "role":
                    project_meta[
                        "role"
                    ],

                "license":
                    project_meta[
                        "license"
                    ],

                "release_kind":
                    release_kind,

                "version_id":
                    version_id,

                "version_number":
                    version_number,

                "jar_filename":
                    jar_path.name,

                "relative_path":
                    relative_path,

                "modality":
                    modality,

                "size_bytes":
                    int(
                        info.file_size
                    ),

                "compressed_size_bytes":
                    int(
                        info.compress_size
                    ),

                "component_sha256":
                    digest,
            })


            counts[
                modality
            ] += 1


            # For very large packages show progress.
            if (
                total_entries >= 5000
                and
                entry_index % 5000 == 0
            ):

                print(
                    "      scanned entries:",
                    f"{entry_index}/"
                    f"{total_entries}"
                )


    print(
        "    JAR scan complete"
    )


    return (
        rows,
        dict(
            counts
        ),
    )


# =========================================================
# Read Phase 6A corpus
# =========================================================

if not INPUT_CSV.exists():

    raise FileNotFoundError(
        f"Missing: {INPUT_CSV}"
    )


fresh = pd.read_csv(
    INPUT_CSV
)


required_columns = {
    "fresh_id",
    "project_id",
    "slug",
    "title",
    "role",
    "license",

    "current_version_id",
    "current_version_number",
    "current_date_published",
    "current_filename",
    "current_url",
    "current_sha1",
    "current_sha512",

    "historical_version_ids",
    "historical_version_numbers",
    "historical_dates",
    "historical_filenames",
    "historical_urls",
    "historical_sha1",
    "historical_sha512",
}


missing = (
    required_columns
    - set(
        fresh.columns
    )
)


if missing:

    raise RuntimeError(
        "Missing columns: "
        + ", ".join(
            sorted(
                missing
            )
        )
    )


print(
    "======================================"
)

print(
    "Phase 6B - Fresh JAR Registry"
)

print(
    "======================================"
)

print(
    "Projects:",
    len(fresh)
)

print(
    "Expected current JARs:",
    len(fresh)
)

print(
    "Expected historical JARs:",
    len(fresh) * 3
)


# =========================================================
# Main storage
# =========================================================

current_package_rows = []

historical_package_rows = []

current_component_rows = []

historical_component_rows = []

failures = []


current_download_ok = 0

historical_download_ok = 0

current_bytes = 0

historical_bytes = 0


# =========================================================
# Process projects
# =========================================================

for project_number, (
    _,
    row
) in enumerate(
    fresh.iterrows(),
    start=1,
):

    meta = {
        "fresh_id":
            clean_text(
                row[
                    "fresh_id"
                ]
            ),

        "project_id":
            clean_text(
                row[
                    "project_id"
                ]
            ),

        "slug":
            clean_text(
                row[
                    "slug"
                ]
            ),

        "title":
            clean_text(
                row[
                    "title"
                ]
            ),

        "role":
            clean_text(
                row[
                    "role"
                ]
            ),

        "license":
            clean_text(
                row[
                    "license"
                ]
            ),
    }


    print()

    print(
        "======================================"
    )

    print(
        f"[{project_number}/"
        f"{len(fresh)}] "
        f"{meta['fresh_id']} "
        f"{meta['title']}"
    )

    print(
        "======================================"
    )


    # =====================================================
    # Current release
    # =====================================================

    current_filename = (
        Path(
            clean_text(
                row[
                    "current_filename"
                ]
            )
        ).name
    )


    current_path = (
        CURRENT_ROOT
        / meta[
            "fresh_id"
        ]
        / current_filename
    )


    print(
        "  CURRENT"
    )


    result = download_file(
        clean_text(
            row[
                "current_url"
            ]
        ),

        current_path,

        clean_text(
            row[
                "current_sha1"
            ]
        ),

        clean_text(
            row[
                "current_sha512"
            ]
        ),
    )


    if not result[
        "ok"
    ]:

        print(
            "  CURRENT FAILED:",
            result.get(
                "error"
            )
        )


        failures.append({
            "fresh_id":
                meta[
                    "fresh_id"
                ],

            "project_id":
                meta[
                    "project_id"
                ],

            "release_kind":
                "CURRENT",

            "version_id":
                clean_text(
                    row[
                        "current_version_id"
                    ]
                ),

            "filename":
                current_filename,

            "reason":
                "download_failed",

            "detail":
                result.get(
                    "error"
                ),
        })


    else:

        current_download_ok += 1

        current_bytes += int(
            result[
                "bytes"
            ]
        )


        try:

            component_rows, counts = (
                scan_jar(
                    current_path,
                    meta,
                    "CURRENT",

                    clean_text(
                        row[
                            "current_version_id"
                        ]
                    ),

                    clean_text(
                        row[
                            "current_version_number"
                        ]
                    ),
                )
            )


            current_component_rows.extend(
                component_rows
            )


            current_package_rows.append({
                **meta,

                "release_kind":
                    "CURRENT",

                "version_id":
                    clean_text(
                        row[
                            "current_version_id"
                        ]
                    ),

                "version_number":
                    clean_text(
                        row[
                            "current_version_number"
                        ]
                    ),

                "date_published":
                    clean_text(
                        row[
                            "current_date_published"
                        ]
                    ),

                "filename":
                    current_filename,

                "local_path":
                    str(
                        current_path
                    ),

                "source_url":
                    clean_text(
                        row[
                            "current_url"
                        ]
                    ),

                "expected_sha1":
                    clean_text(
                        row[
                            "current_sha1"
                        ]
                    ),

                "expected_sha512":
                    clean_text(
                        row[
                            "current_sha512"
                        ]
                    ),

                "download_sha256":
                    result[
                        "sha256"
                    ],

                "download_bytes":
                    int(
                        result[
                            "bytes"
                        ]
                    ),

                "download_status":
                    result[
                        "status"
                    ],

                "code_binary_components":
                    int(
                        counts.get(
                            "CODE_BINARY",
                            0
                        )
                    ),

                "structured_components":
                    int(
                        counts.get(
                            "STRUCTURED",
                            0
                        )
                    ),

                "image_components":
                    int(
                        counts.get(
                            "IMAGE",
                            0
                        )
                    ),
            })


            print(
                "  current:",
                result[
                    "status"
                ],
                "code=",
                counts.get(
                    "CODE_BINARY",
                    0
                ),
                "structured=",
                counts.get(
                    "STRUCTURED",
                    0
                ),
                "image=",
                counts.get(
                    "IMAGE",
                    0
                ),
            )


        except Exception as exc:

            print(
                "  CURRENT JAR ERROR:",
                repr(exc)
            )


            failures.append({
                "fresh_id":
                    meta[
                        "fresh_id"
                    ],

                "project_id":
                    meta[
                        "project_id"
                    ],

                "release_kind":
                    "CURRENT",

                "version_id":
                    clean_text(
                        row[
                            "current_version_id"
                        ]
                    ),

                "filename":
                    current_filename,

                "reason":
                    "jar_scan_failed",

                "detail":
                    repr(exc),
            })


    # =====================================================
    # Historical metadata
    # =====================================================

    historical_version_ids = json_list(
        row[
            "historical_version_ids"
        ]
    )

    historical_version_numbers = json_list(
        row[
            "historical_version_numbers"
        ]
    )

    historical_dates = json_list(
        row[
            "historical_dates"
        ]
    )

    historical_filenames = json_list(
        row[
            "historical_filenames"
        ]
    )

    historical_urls = json_list(
        row[
            "historical_urls"
        ]
    )

    historical_sha1 = json_list(
        row[
            "historical_sha1"
        ]
    )

    historical_sha512 = json_list(
        row[
            "historical_sha512"
        ]
    )


    lists = [
        historical_version_ids,
        historical_version_numbers,
        historical_dates,
        historical_filenames,
        historical_urls,
        historical_sha1,
        historical_sha512,
    ]


    if any(
        len(values) < 3
        for values
        in lists
    ):

        print(
            "  HISTORICAL METADATA "
            "INCOMPLETE"
        )


        failures.append({
            "fresh_id":
                meta[
                    "fresh_id"
                ],

            "project_id":
                meta[
                    "project_id"
                ],

            "release_kind":
                "HISTORICAL",

            "reason":
                "historical_metadata_incomplete",

            "lengths":
                [
                    len(values)
                    for values
                    in lists
                ],
        })

        continue


    # =====================================================
    # Historical 1..3
    # =====================================================

    for historical_index in range(
        3
    ):

        rank = (
            historical_index + 1
        )

        version_id = clean_text(
            historical_version_ids[
                historical_index
            ]
        )

        version_number = clean_text(
            historical_version_numbers[
                historical_index
            ]
        )

        date_published = clean_text(
            historical_dates[
                historical_index
            ]
        )

        filename = (
            Path(
                clean_text(
                    historical_filenames[
                        historical_index
                    ]
                )
            ).name
        )

        url = clean_text(
            historical_urls[
                historical_index
            ]
        )

        sha1 = clean_text(
            historical_sha1[
                historical_index
            ]
        )

        sha512 = clean_text(
            historical_sha512[
                historical_index
            ]
        )


        destination = (
            HISTORICAL_ROOT
            / meta[
                "fresh_id"
            ]
            / version_id
            / filename
        )


        print()

        print(
            f"  HISTORICAL {rank}"
        )

        print(
            "    version:",
            version_number
        )

        print(
            "    filename:",
            filename
        )


        result = download_file(
            url,
            destination,
            sha1,
            sha512,
        )


        if not result[
            "ok"
        ]:

            print(
                "  historical",
                rank,
                "FAILED:",
                result.get(
                    "error"
                )
            )


            failures.append({
                "fresh_id":
                    meta[
                        "fresh_id"
                    ],

                "project_id":
                    meta[
                        "project_id"
                    ],

                "release_kind":
                    "HISTORICAL",

                "version_id":
                    version_id,

                "filename":
                    filename,

                "reason":
                    "download_failed",

                "detail":
                    result.get(
                        "error"
                    ),
            })

            continue


        historical_download_ok += 1

        historical_bytes += int(
            result[
                "bytes"
            ]
        )


        try:

            component_rows, counts = (
                scan_jar(
                    destination,
                    meta,
                    "HISTORICAL",
                    version_id,
                    version_number,
                )
            )


            historical_component_rows.extend(
                component_rows
            )


            historical_package_rows.append({
                **meta,

                "release_kind":
                    "HISTORICAL",

                "historical_rank":
                    rank,

                "version_id":
                    version_id,

                "version_number":
                    version_number,

                "date_published":
                    date_published,

                "filename":
                    filename,

                "local_path":
                    str(
                        destination
                    ),

                "source_url":
                    url,

                "expected_sha1":
                    sha1,

                "expected_sha512":
                    sha512,

                "download_sha256":
                    result[
                        "sha256"
                    ],

                "download_bytes":
                    int(
                        result[
                            "bytes"
                        ]
                    ),

                "download_status":
                    result[
                        "status"
                    ],

                "code_binary_components":
                    int(
                        counts.get(
                            "CODE_BINARY",
                            0
                        )
                    ),

                "structured_components":
                    int(
                        counts.get(
                            "STRUCTURED",
                            0
                        )
                    ),

                "image_components":
                    int(
                        counts.get(
                            "IMAGE",
                            0
                        )
                    ),
            })


            print(
                "  historical",
                rank,
                ":",
                result[
                    "status"
                ],
                "code=",
                counts.get(
                    "CODE_BINARY",
                    0
                ),
                "structured=",
                counts.get(
                    "STRUCTURED",
                    0
                ),
                "image=",
                counts.get(
                    "IMAGE",
                    0
                ),
            )


        except Exception as exc:

            print(
                "  HISTORICAL JAR ERROR:",
                repr(exc)
            )


            failures.append({
                "fresh_id":
                    meta[
                        "fresh_id"
                    ],

                "project_id":
                    meta[
                        "project_id"
                    ],

                "release_kind":
                    "HISTORICAL",

                "version_id":
                    version_id,

                "filename":
                    filename,

                "reason":
                    "jar_scan_failed",

                "detail":
                    repr(exc),
            })


# =========================================================
# Registry DataFrames
# =========================================================

current_packages = pd.DataFrame(
    current_package_rows
)

historical_packages = pd.DataFrame(
    historical_package_rows
)

current_components = pd.DataFrame(
    current_component_rows
)

historical_components = pd.DataFrame(
    historical_component_rows
)


current_packages.to_csv(
    CURRENT_PACKAGE_CSV,
    index=False,
    encoding="utf-8-sig",
)

historical_packages.to_csv(
    HISTORICAL_PACKAGE_CSV,
    index=False,
    encoding="utf-8-sig",
)

current_components.to_csv(
    CURRENT_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)

historical_components.to_csv(
    HISTORICAL_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Current cross-project exact duplicate analysis
# =========================================================

duplicate_rows = []

duplicate_group_count = 0

duplicate_component_count = 0


if len(
    current_components
):

    grouped = (
        current_components
        .groupby(
            [
                "modality",
                "component_sha256",
            ],
            sort=False,
        )
    )


    for (
        modality,
        digest
    ), group in grouped:

        projects = sorted(
            set(
                group[
                    "fresh_id"
                ]
                .astype(str)
            )
        )


        if len(
            projects
        ) <= 1:

            continue


        duplicate_group_count += 1

        duplicate_component_count += (
            len(group)
        )


        for _, duplicate in (
            group.iterrows()
        ):

            duplicate_rows.append({
                "modality":
                    modality,

                "component_sha256":
                    digest,

                "project_count":
                    len(
                        projects
                    ),

                "projects":
                    json.dumps(
                        projects
                    ),

                "fresh_id":
                    duplicate[
                        "fresh_id"
                    ],

                "role":
                    duplicate[
                        "role"
                    ],

                "relative_path":
                    duplicate[
                        "relative_path"
                    ],
            })


duplicate_df = pd.DataFrame(
    duplicate_rows
)


duplicate_df.to_csv(
    DUPLICATE_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary helpers
# =========================================================

def modality_count(
    df,
    modality
):

    if not len(df):
        return 0


    return int(
        (
            df[
                "modality"
            ]
            == modality
        ).sum()
    )


def projects_with_modality(
    df,
    modality
):

    if not len(df):
        return 0


    return int(
        df[
            df[
                "modality"
            ]
            == modality
        ][
            "fresh_id"
        ].nunique()
    )


# =========================================================
# Summary counts
# =========================================================

target_current_components = 0

background_current_components = 0


if len(
    current_components
):

    target_current_components = int(
        (
            current_components[
                "role"
            ]
            == "TARGET_MOD"
        ).sum()
    )


    background_current_components = int(
        (
            current_components[
                "role"
            ]
            == "BACKGROUND_LIBRARY"
        ).sum()
    )


duplicate_rate = (
    duplicate_component_count
    / len(
        current_components
    )

    if len(
        current_components
    )

    else 0.0
)


current_component_counts = []


if len(
    current_components
):

    current_component_counts = (
        current_components
        .groupby(
            "fresh_id"
        )
        .size()
        .tolist()
    )


# =========================================================
# Summary
# =========================================================

summary = {
    "fresh_projects_requested":
        len(
            fresh
        ),

    "current_jars_expected":
        len(
            fresh
        ),

    "historical_jars_expected":
        len(
            fresh
        ) * 3,

    "current_jars_downloaded":
        current_download_ok,

    "historical_jars_downloaded":
        historical_download_ok,

    "current_packages_scanned":
        len(
            current_packages
        ),

    "historical_packages_scanned":
        len(
            historical_packages
        ),

    "failures":
        len(
            failures
        ),

    "current_download_bytes":
        int(
            current_bytes
        ),

    "historical_download_bytes":
        int(
            historical_bytes
        ),

    "current_components_total":
        len(
            current_components
        ),

    "current_code_binary":
        modality_count(
            current_components,
            "CODE_BINARY"
        ),

    "current_structured":
        modality_count(
            current_components,
            "STRUCTURED"
        ),

    "current_image":
        modality_count(
            current_components,
            "IMAGE"
        ),

    "historical_components_total":
        len(
            historical_components
        ),

    "historical_code_binary":
        modality_count(
            historical_components,
            "CODE_BINARY"
        ),

    "historical_structured":
        modality_count(
            historical_components,
            "STRUCTURED"
        ),

    "historical_image":
        modality_count(
            historical_components,
            "IMAGE"
        ),

    "target_current_components":
        target_current_components,

    "background_current_components":
        background_current_components,

    "current_projects_with_code":
        projects_with_modality(
            current_components,
            "CODE_BINARY"
        ),

    "current_projects_with_structured":
        projects_with_modality(
            current_components,
            "STRUCTURED"
        ),

    "current_projects_with_image":
        projects_with_modality(
            current_components,
            "IMAGE"
        ),

    "median_current_components_per_project":
        (
            float(
                statistics.median(
                    current_component_counts
                )
            )
            if current_component_counts
            else 0.0
        ),

    "current_cross_project_duplicate_groups":
        int(
            duplicate_group_count
        ),

    "current_cross_project_duplicate_components":
        int(
            duplicate_component_count
        ),

    "current_cross_project_duplicate_rate":
        float(
            duplicate_rate
        ),

    "goals_met":
        bool(
            len(fresh) == 120

            and
            current_download_ok == 120

            and
            historical_download_ok == 360

            and
            len(
                current_packages
            ) == 120

            and
            len(
                historical_packages
            ) == 360

            and
            len(
                failures
            ) == 0
        ),
}


FAILURE_JSON.write_text(
    json.dumps(
        failures,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


SUMMARY_JSON.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Result
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 6B RESULT"
)

print(
    "======================================"
)


print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )
)


print()

print(
    "Current packages   :",
    CURRENT_PACKAGE_CSV
)

print(
    "Historical packages:",
    HISTORICAL_PACKAGE_CSV
)

print(
    "Current components :",
    CURRENT_COMPONENT_CSV
)

print(
    "History components :",
    HISTORICAL_COMPONENT_CSV
)

print(
    "Duplicates         :",
    DUPLICATE_CSV
)

print(
    "Failures           :",
    FAILURE_JSON
)

print(
    "Summary            :",
    SUMMARY_JSON
)