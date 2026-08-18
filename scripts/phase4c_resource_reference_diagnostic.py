import json
import re
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


PACKAGE_REGISTRY = Path(
    "data/registry/release_package_registry.csv"
)

RELEASE_ROOT = Path(
    "data/release_packages"
)

RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)


IDENTIFIER_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"([a-z0-9_.-]+:[a-z0-9_./-]+)"
)


# =========================================================
# Constant pool UTF8 extraction
# =========================================================

def u1(data, pos):
    return data[pos], pos + 1


def u2(data, pos):
    return (
        struct.unpack_from(
            ">H", data, pos
        )[0],
        pos + 2
    )


def extract_utf8(data):

    if len(data) < 10:
        return []

    if data[:4] != b"\xca\xfe\xba\xbe":
        return []

    pos = 4

    _, pos = u2(data, pos)
    _, pos = u2(data, pos)

    cp_count, pos = u2(
        data, pos
    )

    values = []

    i = 1

    try:

        while i < cp_count:

            tag = data[pos]
            pos += 1

            if tag == 1:

                length, pos = u2(
                    data, pos
                )

                raw = data[
                    pos:pos + length
                ]

                pos += length

                values.append(
                    raw.decode(
                        "utf-8",
                        errors="replace"
                    )
                )

            elif tag in (3, 4):
                pos += 4

            elif tag in (5, 6):
                pos += 8
                i += 1

            elif tag in (
                7, 8, 16, 19, 20
            ):
                pos += 2

            elif tag in (
                9, 10, 11,
                12, 17, 18
            ):
                pos += 4

            elif tag == 15:
                pos += 3

            else:
                break

            i += 1

    except Exception:
        pass

    return values


# =========================================================
# JSON strings
# =========================================================

def walk_json(obj, parent_key=None):

    if isinstance(obj, dict):

        for key, value in obj.items():

            yield from walk_json(
                value,
                str(key)
            )

    elif isinstance(obj, list):

        for value in obj:

            yield from walk_json(
                value,
                parent_key
            )

    elif isinstance(obj, str):

        yield parent_key, obj


# =========================================================
# Internal resource index
# =========================================================

def resource_identifiers(paths):

    identifiers = defaultdict(set)

    for path in paths:

        lower = (
            path.replace("\\", "/")
            .lower()
        )

        parts = lower.split("/")

        # assets/<namespace>/<type>/...
        if (
            len(parts) >= 4
            and
            parts[0] == "assets"
        ):

            namespace = parts[1]
            resource_type = parts[2]

            rest = "/".join(
                parts[3:]
            )

            stem = rest

            for suffix in (
                ".json",
                ".png",
                ".jpg",
                ".jpeg",
                ".mcmeta",
            ):

                if stem.endswith(suffix):
                    stem = stem[:-len(suffix)]
                    break

            # Minecraft identifier style
            identifiers[
                f"{namespace}:{stem}"
            ].add(path)

            identifiers[
                f"{namespace}:"
                f"{resource_type}/{stem}"
            ].add(path)


        # data/<namespace>/<type>/...
        elif (
            len(parts) >= 4
            and
            parts[0] == "data"
        ):

            namespace = parts[1]
            resource_type = parts[2]

            rest = "/".join(
                parts[3:]
            )

            stem = rest

            if stem.endswith(".json"):
                stem = stem[:-5]

            identifiers[
                f"{namespace}:{stem}"
            ].add(path)

            identifiers[
                f"{namespace}:"
                f"{resource_type}/{stem}"
            ].add(path)

    return identifiers


# =========================================================
# Main
# =========================================================

packages = pd.read_csv(
    PACKAGE_REGISTRY
)

mod_rows = []

unresolved_rows = []

global_counts = Counter()


print(
    "======================================"
)
print(
    "Phase 4C - Resource Reference Diagnostic"
)
print(
    "======================================"
)


for index, pkg in packages.iterrows():

    mod_id = pkg["mod_id"]

    jar_path = (
        RELEASE_ROOT
        / mod_id
        / pkg["filename"]
    )

    print()
    print(
        f"[{index + 1}/{len(packages)}] "
        f"{mod_id} - {pkg['title']}"
    )


    with zipfile.ZipFile(
        jar_path, "r"
    ) as jar:

        paths = {
            x.replace("\\", "/")
            for x in jar.namelist()
            if not x.endswith("/")
        }

        resource_index = (
            resource_identifiers(
                paths
            )
        )

        counts = Counter()


        # =================================================
        # JSON identifiers
        # =================================================

        for path in paths:

            if not path.lower().endswith(
                ".json"
            ):
                continue

            try:

                obj = json.loads(
                    jar.read(path).decode(
                        "utf-8"
                    )
                )

            except Exception:
                continue


            for key, text in walk_json(
                obj
            ):

                matches = (
                    IDENTIFIER_RE.findall(
                        text.lower()
                    )
                )

                for identifier in matches:

                    counts[
                        "json_identifiers"
                    ] += 1

                    namespace = (
                        identifier.split(
                            ":",
                            1
                        )[0]
                    )

                    if namespace == "minecraft":

                        counts[
                            "json_external_minecraft"
                        ] += 1

                    if identifier in (
                        resource_index
                    ):

                        counts[
                            "json_internal_resolvable"
                        ] += 1

                    else:

                        counts[
                            "json_unresolved"
                        ] += 1

                        if (
                            len(
                                unresolved_rows
                            )
                            < 5000
                        ):

                            unresolved_rows.append({

                                "mod_id":
                                    mod_id,

                                "source":
                                    path,

                                "source_type":
                                    "JSON",

                                "key":
                                    key,

                                "identifier":
                                    identifier,

                                "namespace":
                                    namespace,
                            })


        # =================================================
        # Class constant identifiers
        # =================================================

        for path in paths:

            if not path.lower().endswith(
                ".class"
            ):
                continue

            if path.lower().startswith(
                "meta-inf/"
            ):
                continue

            try:

                strings = extract_utf8(
                    jar.read(path)
                )

            except Exception:
                continue


            for text in strings:

                matches = (
                    IDENTIFIER_RE.findall(
                        text.lower()
                    )
                )

                for identifier in matches:

                    counts[
                        "class_identifiers"
                    ] += 1

                    namespace = (
                        identifier.split(
                            ":",
                            1
                        )[0]
                    )

                    if namespace == "minecraft":

                        counts[
                            "class_external_minecraft"
                        ] += 1

                    if identifier in (
                        resource_index
                    ):

                        counts[
                            "class_internal_resolvable"
                        ] += 1

                    else:

                        counts[
                            "class_unresolved"
                        ] += 1

                        if (
                            len(
                                unresolved_rows
                            )
                            < 5000
                        ):

                            unresolved_rows.append({

                                "mod_id":
                                    mod_id,

                                "source":
                                    path,

                                "source_type":
                                    "CLASS",

                                "key":
                                    None,

                                "identifier":
                                    identifier,

                                "namespace":
                                    namespace,
                            })


        # =================================================
        # Counts
        # =================================================

        counts[
            "indexed_resource_identifiers"
        ] = len(
            resource_index
        )

        global_counts.update(
            counts
        )


        mod_rows.append({

            "mod_id":
                mod_id,

            "title":
                pkg["title"],

            "role":
                pkg["role"],

            **dict(counts),
        })


        print(
            "JSON ids="
            f"{counts['json_identifiers']} "
            "internal="
            f"{counts['json_internal_resolvable']} "
            "class ids="
            f"{counts['class_identifiers']} "
            "internal="
            f"{counts['class_internal_resolvable']}"
        )


# =========================================================
# Save
# =========================================================

mods = pd.DataFrame(
    mod_rows
)

unresolved = pd.DataFrame(
    unresolved_rows
)


mods.to_csv(

    RESULT_ROOT
    / "resource_reference_diagnostic.csv",

    index=False,
    encoding="utf-8-sig",
)


unresolved.to_csv(

    RESULT_ROOT
    / "resource_reference_unresolved.csv",

    index=False,
    encoding="utf-8-sig",
)


summary = {

    "projects":
        len(mods),

    "json_identifiers":
        int(
            global_counts[
                "json_identifiers"
            ]
        ),

    "json_internal_resolvable":
        int(
            global_counts[
                "json_internal_resolvable"
            ]
        ),

    "json_external_minecraft":
        int(
            global_counts[
                "json_external_minecraft"
            ]
        ),

    "json_unresolved":
        int(
            global_counts[
                "json_unresolved"
            ]
        ),

    "class_identifiers":
        int(
            global_counts[
                "class_identifiers"
            ]
        ),

    "class_internal_resolvable":
        int(
            global_counts[
                "class_internal_resolvable"
            ]
        ),

    "class_external_minecraft":
        int(
            global_counts[
                "class_external_minecraft"
            ]
        ),

    "class_unresolved":
        int(
            global_counts[
                "class_unresolved"
            ]
        ),

    "mods_with_internal_json_refs":
        int(
            (
                mods.get(
                    "json_internal_resolvable",
                    pd.Series(
                        [0] * len(mods)
                    )
                )
                .fillna(0)
                > 0
            ).sum()
        ),

    "mods_with_internal_class_refs":
        int(
            (
                mods.get(
                    "class_internal_resolvable",
                    pd.Series(
                        [0] * len(mods)
                    )
                )
                .fillna(0)
                > 0
            ).sum()
        ),
}


(
    RESULT_ROOT
    / "phase4c_summary.json"
).write_text(

    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    ),

    encoding="utf-8"
)


print()
print(
    "======================================"
)
print(
    "RESULT"
)
print(
    "======================================"
)

print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    )
)