import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


CURRENT_COMPONENTS = Path(
    "data/registry/release_component_registry.csv"
)

CURRENT_PACKAGES = Path(
    "data/registry/release_package_registry.csv"
)

HISTORY_RESULTS = Path(
    "results/real_version_component_results.csv"
)

HISTORY_ROOT = Path(
    "data/historical_releases"
)

RELEASE_ROOT = Path(
    "data/release_packages"
)

RESULT_ROOT = Path("results")
TOOLS_ROOT = Path("tools/phase3d")

RESULT_ROOT.mkdir(exist_ok=True)
TOOLS_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

JAVA_SOURCE = (
    TOOLS_ROOT / "JavapBatch.java"
)

JAVA_CLASS = (
    TOOLS_ROOT / "JavapBatch.class"
)

BATCH_SIZE = 40


# =========================================================
# Java helper
# =========================================================

JAVA_CODE = r'''
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.Optional;
import java.util.spi.ToolProvider;

public class JavapBatch {

    public static void main(
        String[] args
    ) {

        if (args.length < 2) {

            System.err.println(
                "Usage: JavapBatch "
                + "<jar> <class> [class...]"
            );

            System.exit(2);
        }

        Optional<ToolProvider> maybe =
            ToolProvider.findFirst(
                "javap"
            );

        if (maybe.isEmpty()) {

            System.err.println(
                "javap ToolProvider "
                + "not found"
            );

            System.exit(3);
        }

        ToolProvider javap =
            maybe.get();

        String jar = args[0];

        for (
            int i = 1;
            i < args.length;
            i++
        ) {

            String cls = args[i];

            System.out.println(
                "@@BEGIN\t" + cls
            );

            StringWriter outBuffer =
                new StringWriter();

            StringWriter errBuffer =
                new StringWriter();

            PrintWriter out =
                new PrintWriter(
                    outBuffer
                );

            PrintWriter err =
                new PrintWriter(
                    errBuffer
                );

            int rc = javap.run(
                out,
                err,

                "-classpath",
                jar,

                "-c",
                "-p",
                "-s",

                cls
            );

            out.flush();
            err.flush();

            System.out.print(
                outBuffer.toString()
            );

            String errText =
                errBuffer.toString();

            if (!errText.isBlank()) {

                System.out.println(
                    "@@JAVAP_ERROR"
                );

                System.out.print(
                    errText
                );
            }

            System.out.println(
                "@@END\t"
                + cls
                + "\t"
                + rc
            );
        }
    }
}
'''


def ensure_java_helper():

    JAVA_SOURCE.write_text(
        JAVA_CODE,
        encoding="utf-8"
    )

    print(
        "[SETUP] Compiling "
        "Java helper..."
    )

    result = subprocess.run(
        [
            "javac",
            str(JAVA_SOURCE)
        ],

        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,

        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:

        raise RuntimeError(
            "javac failed:\n"
            + result.stdout
            + "\n"
            + result.stderr
        )


# =========================================================
# javap helpers
# =========================================================

def path_to_class_name(path):

    p = str(path).replace(
        "\\",
        "/"
    )

    if not p.lower().endswith(
        ".class"
    ):
        return None

    if p.lower().endswith(
        "module-info.class"
    ):
        return None

    return (
        p[:-6]
        .replace("/", ".")
    )


def chunks(items, size):

    for i in range(
        0,
        len(items),
        size
    ):

        yield items[
            i:i + size
        ]


def parse_marked_output(text):

    blocks = {}

    current_name = None
    current_lines = []

    for line in text.splitlines():

        if line.startswith(
            "@@BEGIN\t"
        ):

            current_name = (
                line.split(
                    "\t",
                    1
                )[1]
            )

            current_lines = []

            continue

        if line.startswith(
            "@@END\t"
        ):

            parts = (
                line.split("\t")
            )

            if current_name is not None:

                try:
                    rc = int(
                        parts[-1]
                    )

                except Exception:
                    rc = 1

                blocks[
                    current_name
                ] = {

                    "rc":
                        rc,

                    "text":
                        "\n".join(
                            current_lines
                        ),
                }

            current_name = None
            current_lines = []

            continue

        if current_name is not None:

            current_lines.append(
                line
            )

    return blocks


def run_javap_for_classes(
    jar_path,
    class_names
):

    class_names = list(
        dict.fromkeys(
            class_names
        )
    )

    output = {}

    for batch in chunks(
        class_names,
        BATCH_SIZE
    ):

        cmd = [

            "java",

            "--add-modules",
            "jdk.jdeps",

            "-Dfile.encoding=UTF-8",

            "-cp",
            str(TOOLS_ROOT),

            "JavapBatch",

            str(jar_path),

            *batch,
        ]

        result = subprocess.run(

            cmd,

            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,

            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:

            print(
                "[WARNING] "
                "Java helper failed:"
            )

            print(
                result.stderr[-500:]
            )

            continue

        output.update(
            parse_marked_output(
                result.stdout
            )
        )

    return output


# =========================================================
# Bytecode feature extraction
# =========================================================

INSTRUCTION_RE = re.compile(
    r"^\s*\d+:\s+"
    r"([a-z][a-z0-9_]*)"
    r"\b(.*)$"
)

OBJECT_DESC_RE = re.compile(
    r"L[^;]+;"
)


def normalize_descriptor(desc):

    # 실제 class/package 이름을 제거한다.
    #
    # 예:
    #
    # (Lnet/minecraft/X;)V
    #
    # →
    #
    # (LREF;)V

    return OBJECT_DESC_RE.sub(
        "LREF;",
        desc
    )


def operand_category(
    opcode,
    rest
):

    rest_lower = (
        rest.lower()
    )

    if (
        "// interfacemethod"
        in rest_lower
        or
        "// method"
        in rest_lower
    ):
        return "CALL"

    if (
        "// invokedynamic"
        in rest_lower
    ):
        return "DYNAMIC_CALL"

    if "// field" in rest_lower:
        return "FIELD"

    if "// class" in rest_lower:
        return "TYPE"

    if "// string" in rest_lower:
        return "STRING_CONST"

    numeric_tokens = [
        "// int ",
        "// long ",
        "// float ",
        "// double ",
    ]

    if any(
        x in rest_lower
        for x in numeric_tokens
    ):
        return "NUM_CONST"

    if (
        opcode.startswith("if")
        or opcode
        in {
            "goto",
            "goto_w",
            "jsr",
            "jsr_w",
            "tableswitch",
            "lookupswitch",
        }
    ):
        return "BRANCH"

    if (
        "load" in opcode
        or "store" in opcode
        or opcode == "iinc"
    ):
        return "LOCAL"

    if opcode in {
        "new",
        "anewarray",
        "newarray",
        "multianewarray",
        "checkcast",
        "instanceof",
    }:
        return "TYPE_OP"

    if opcode in {
        "ldc",
        "ldc_w",
        "ldc2_w",
        "bipush",
        "sipush",
    }:
        return "CONST"

    return "NONE"


def bucket(n):

    if n <= 0:
        return "0"

    if n == 1:
        return "1"

    if n <= 3:
        return "2-3"

    if n <= 7:
        return "4-7"

    if n <= 15:
        return "8-15"

    if n <= 31:
        return "16-31"

    if n <= 63:
        return "32-63"

    if n <= 127:
        return "64-127"

    if n <= 255:
        return "128-255"

    if n <= 511:
        return "256-511"

    return "512+"


def javap_features(text):

    opcodes = []
    context = []
    descriptors = []

    for line in text.splitlines():

        stripped = (
            line.strip()
        )

        if stripped.startswith(
            "descriptor:"
        ):

            desc = (
                stripped
                .split(
                    ":",
                    1
                )[1]
                .strip()
            )

            descriptors.append(
                normalize_descriptor(
                    desc
                )
            )

            continue

        match = (
            INSTRUCTION_RE.match(
                line
            )
        )

        if not match:
            continue

        opcode = (
            match.group(1)
        )

        rest = (
            match.group(2)
        )

        opcodes.append(
            opcode
        )

        category = (
            operand_category(
                opcode,
                rest
            )
        )

        context.append(
            f"{opcode}:{category}"
        )

    # -----------------------------------------------------
    # Representation 1
    # Opcode 3-gram
    # -----------------------------------------------------

    op3 = []

    if len(opcodes) >= 3:

        for i in range(
            len(opcodes) - 2
        ):

            op3.append(
                "OP3:"
                + ">".join(
                    opcodes[
                        i:i + 3
                    ]
                )
            )

    else:

        op3.extend(
            "OP1:" + op
            for op in opcodes
        )

    # -----------------------------------------------------
    # Representation 2
    # Opcode + structural information
    # -----------------------------------------------------

    struct = list(op3)

    struct.extend(
        "DESC:" + d
        for d in descriptors
    )

    struct.append(
        "METHOD_COUNT:"
        + bucket(
            len(descriptors)
        )
    )

    struct.append(
        "OP_COUNT:"
        + bucket(
            len(opcodes)
        )
    )

    opcode_counts = Counter(
        opcodes
    )

    for op, count in (
        opcode_counts.items()
    ):

        struct.append(
            f"OPCOUNT:{op}:"
            f"{bucket(count)}"
        )

    # -----------------------------------------------------
    # Representation 3
    # Opcode + normalized operand context
    # -----------------------------------------------------

    contextual = list(op3)

    contextual.extend(
        "CTX:" + x
        for x in context
    )

    contextual.extend(
        "DESC:" + d
        for d in descriptors
    )

    contextual.append(
        "METHOD_COUNT:"
        + bucket(
            len(descriptors)
        )
    )

    contextual.append(
        "OP_COUNT:"
        + bucket(
            len(opcodes)
        )
    )

    return {

        "OPCODE_3GRAM":
            op3,

        "OPCODE_STRUCT":
            struct,

        "OPCODE_CONTEXT":
            contextual,
    }


# =========================================================
# 128-bit SimHash
# =========================================================

def simhash128(features):

    counts = Counter(
        features
    )

    if not counts:
        return 0

    vector = [0] * 128

    for feature, count in (
        counts.items()
    ):

        raw = feature.encode(
            "utf-8",
            errors="ignore"
        )

        digest = (
            hashlib.blake2b(
                raw,
                digest_size=16,
                person=b"MODPROV3D",
            )
            .digest()
        )

        value = int.from_bytes(
            digest,
            "big"
        )

        weight = min(
            int(count),
            8
        )

        for bit in range(128):

            if value & (
                1 << bit
            ):

                vector[bit] += (
                    weight
                )

            else:

                vector[bit] -= (
                    weight
                )

    result = 0

    for bit, value in enumerate(
        vector
    ):

        if value >= 0:

            result |= (
                1 << bit
            )

    return result


def signatures_from_javap(
    text
):

    features = (
        javap_features(text)
    )

    return {

        name:
            simhash128(feats)

        for name, feats
        in features.items()
    }


def hamming128(a, b):

    return (
        int(a) ^ int(b)
    ).bit_count()


# =========================================================
# Historical JAR
# =========================================================

def find_historical_jar(
    mod_id,
    version_id
):

    directory = (
        HISTORY_ROOT
        / str(mod_id)
        / str(version_id)
    )

    jars = list(
        directory.glob(
            "*.jar"
        )
    )

    if not jars:
        return None

    return jars[0]


# =========================================================
# Retrieval
# =========================================================

def evaluate_representation(
    rep_name,
    query_sig,
    true_mod,
    gallery
):

    distance_by_mod = {}

    # 각 MOD에서 가장 유사한
    # component 하나를 대표 점수로 사용
    for (
        mod_id,
        signatures
    ) in gallery.items():

        if not signatures:
            continue

        best = min(

            hamming128(
                query_sig,
                candidate_sig
            )

            for candidate_sig
            in signatures
        )

        distance_by_mod[
            mod_id
        ] = best

    if (
        true_mod
        not in distance_by_mod
        or
        not distance_by_mod
    ):
        return None

    true_distance = (
        distance_by_mod[
            true_mod
        ]
    )

    best_distance = min(
        distance_by_mod.values()
    )

    best_mods = sorted(

        mod_id

        for mod_id, distance
        in distance_by_mod.items()

        if distance
        == best_distance
    )

    distinct = sorted(
        set(
            distance_by_mod.values()
        )
    )

    if len(distinct) >= 2:

        second_distance = (
            distinct[1]
        )

    else:

        second_distance = (
            best_distance
        )

    # tie가 있을 때 true parent를
    # 불리하게 랜덤 정렬하지 않기 위해
    # "true보다 확실하게 좋은 MOD 수 + 1"
    # 로 optimistic rank 정의
    better_than_true = sum(

        1

        for distance
        in distance_by_mod.values()

        if distance
        < true_distance
    )

    optimistic_rank = (
        better_than_true + 1
    )

    tied_with_true = sum(

        1

        for distance
        in distance_by_mod.values()

        if distance
        == true_distance
    )

    return {

        "representation":
            rep_name,

        "best_distance":
            best_distance,

        "second_distance":
            second_distance,

        "top1_margin":
            (
                second_distance
                - best_distance
            ),

        "true_distance":
            true_distance,

        "optimistic_rank":
            optimistic_rank,

        "true_tie_size":
            tied_with_true,

        "best_tie_size":
            len(best_mods),

        "top1_unique_correct":
            (
                len(best_mods) == 1
                and
                best_mods[0]
                == true_mod
            ),

        "top1_true_in_tie":
            (
                true_mod
                in best_mods
            ),

        "top3_true":
            (
                optimistic_rank <= 3
            ),

        "top5_true":
            (
                optimistic_rank <= 5
            ),

        "top10_true":
            (
                optimistic_rank <= 10
            ),

        "best_mods":
            "|".join(
                best_mods
            ),
    }


# =========================================================
# Main
# =========================================================

def main():

    ensure_java_helper()

    current = pd.read_csv(
        CURRENT_COMPONENTS
    )

    packages = pd.read_csv(
        CURRENT_PACKAGES
    )

    history = pd.read_csv(
        HISTORY_RESULTS
    )

    current_code = current[
        current["modality"]
        == "CODE_BINARY"
    ].copy()

    history_code = history[
        history["modality"]
        == "CODE_BINARY"
    ].copy()


    # =====================================================
    # Reconstruct Phase 3B hard subset
    # =====================================================

    path_index = defaultdict(
        set
    )

    for _, row in current.iterrows():

        path = str(
            row["relative_path"]
        ).replace(
            "\\",
            "/"
        ).lower()

        path_index[
            path
        ].add(
            row["mod_id"]
        )


    hard_rows = []

    for _, row in (
        history_code.iterrows()
    ):

        true_mod = (
            row["mod_id"]
        )

        path = str(
            row["relative_path"]
        ).replace(
            "\\",
            "/"
        ).lower()

        candidates = (
            path_index.get(
                path,
                set()
            )
        )

        # FULL_PATH가 이미
        # unique correct면 제외
        if (
            len(candidates) == 1
            and
            true_mod in candidates
        ):
            continue

        hard_rows.append(
            row.to_dict()
        )


    hard = pd.DataFrame(
        hard_rows
    )


    print(
        "======================================"
    )

    print(
        "Phase 3D - "
        "Bytecode-aware Hard Baseline"
    )

    print(
        "======================================"
    )

    print(
        "Current code components : "
        f"{len(current_code)}"
    )

    print(
        "Path-failed code queries: "
        f"{len(hard)}"
    )


    package_filename = dict(
        zip(
            packages["mod_id"],
            packages["filename"]
        )
    )


    representations = [

        "OPCODE_3GRAM",

        "OPCODE_STRUCT",

        "OPCODE_CONTEXT",
    ]


    gallery = {

        rep:
            defaultdict(list)

        for rep
        in representations
    }


    current_failures = []


    # =====================================================
    # 1. Current gallery
    # =====================================================

    print()
    print(
        "[1/3] Building "
        "current bytecode gallery..."
    )


    grouped_current = (
        current_code.groupby(
            "mod_id"
        )
    )


    for idx, (
        mod_id,
        group
    ) in enumerate(
        grouped_current,
        start=1
    ):

        filename = (
            package_filename.get(
                mod_id
            )
        )

        if not filename:
            continue

        jar_path = (
            RELEASE_ROOT
            / mod_id
            / filename
        )

        if not jar_path.exists():

            print(
                "[WARNING] "
                f"JAR missing: {jar_path}"
            )

            continue


        class_map = {}
        class_names = []


        for _, row in (
            group.iterrows()
        ):

            class_name = (
                path_to_class_name(
                    row[
                        "relative_path"
                    ]
                )
            )

            if not class_name:
                continue

            class_map[
                class_name
            ] = (
                row[
                    "relative_path"
                ]
            )

            class_names.append(
                class_name
            )


        print(
            f"  [{idx}] "
            f"{mod_id}: "
            f"{len(class_names)} classes"
        )


        outputs = (
            run_javap_for_classes(
                jar_path,
                class_names
            )
        )


        for class_name in (
            class_names
        ):

            block = (
                outputs.get(
                    class_name
                )
            )

            if (
                not block
                or
                block["rc"] != 0
            ):

                current_failures.append({

                    "mod_id":
                        mod_id,

                    "class_name":
                        class_name,

                    "path":
                        class_map.get(
                            class_name
                        ),
                })

                continue


            sigs = (
                signatures_from_javap(
                    block["text"]
                )
            )


            for rep in (
                representations
            ):

                gallery[
                    rep
                ][
                    mod_id
                ].append(
                    sigs[rep]
                )


    for rep in representations:

        count = sum(
            len(v)

            for v
            in gallery[
                rep
            ].values()
        )

        print(
            f"  {rep}: "
            f"{count} indexed"
        )


    # =====================================================
    # 2. Historical hard queries
    # =====================================================

    print()

    print(
        "[2/3] Disassembling "
        "historical hard queries..."
    )


    query_records = []
    historical_failures = []


    grouped = hard.groupby(

        [
            "mod_id",
            "historical_version_id"
        ],

        sort=False
    )


    group_total = len(
        grouped
    )


    for group_idx, (
        (
            mod_id,
            version_id
        ),
        group
    ) in enumerate(
        grouped,
        start=1
    ):

        jar_path = (
            find_historical_jar(
                mod_id,
                version_id
            )
        )


        if jar_path is None:

            for _, row in (
                group.iterrows()
            ):

                historical_failures.append({

                    "mod_id":
                        mod_id,

                    "version_id":
                        version_id,

                    "path":
                        row[
                            "relative_path"
                        ],

                    "reason":
                        "jar_missing",
                })

            continue


        class_to_rows = (
            defaultdict(list)
        )

        class_names = []


        for _, row in (
            group.iterrows()
        ):

            class_name = (
                path_to_class_name(
                    row[
                        "relative_path"
                    ]
                )
            )


            if not class_name:

                historical_failures.append({

                    "mod_id":
                        mod_id,

                    "version_id":
                        version_id,

                    "path":
                        row[
                            "relative_path"
                        ],

                    "reason":
                        "invalid_class_name",
                })

                continue


            class_to_rows[
                class_name
            ].append(
                row.to_dict()
            )

            class_names.append(
                class_name
            )


        class_names = list(
            dict.fromkeys(
                class_names
            )
        )


        print(
            f"  [{group_idx}/"
            f"{group_total}] "
            f"{mod_id}: "
            f"{len(class_names)} classes"
        )


        outputs = (
            run_javap_for_classes(
                jar_path,
                class_names
            )
        )


        for class_name in (
            class_names
        ):

            block = (
                outputs.get(
                    class_name
                )
            )


            if (
                not block
                or
                block["rc"] != 0
            ):

                for row in (
                    class_to_rows[
                        class_name
                    ]
                ):

                    historical_failures.append({

                        "mod_id":
                            mod_id,

                        "version_id":
                            version_id,

                        "path":
                            row[
                                "relative_path"
                            ],

                        "reason":
                            "javap_failed",
                    })

                continue


            sigs = (
                signatures_from_javap(
                    block["text"]
                )
            )


            for row in (
                class_to_rows[
                    class_name
                ]
            ):

                query_records.append({

                    "mod_id":
                        mod_id,

                    "historical_version_id":
                        version_id,

                    "historical_version":
                        row[
                            "historical_version"
                        ],

                    "relative_path":
                        row[
                            "relative_path"
                        ],

                    "signatures":
                        sigs,
                })


    print(
        "Historical query "
        "fingerprints: "
        f"{len(query_records)}"
    )


    # =====================================================
    # 3. Retrieval
    # =====================================================

    print()

    print(
        "[3/3] Evaluating "
        "parent retrieval..."
    )


    raw_rows = []


    for index, query in (
        enumerate(
            query_records,
            start=1
        )
    ):

        true_mod = (
            query["mod_id"]
        )


        for rep in (
            representations
        ):

            evaluated = (
                evaluate_representation(

                    rep,

                    query[
                        "signatures"
                    ][rep],

                    true_mod,

                    gallery[rep],
                )
            )


            if evaluated is None:
                continue


            raw_rows.append({

                "mod_id":
                    true_mod,

                "historical_version_id":
                    query[
                        "historical_version_id"
                    ],

                "historical_version":
                    query[
                        "historical_version"
                    ],

                "relative_path":
                    query[
                        "relative_path"
                    ],

                **evaluated,
            })


        if index % 250 == 0:

            print(
                f"  evaluated "
                f"{index}/"
                f"{len(query_records)}"
            )


    raw = pd.DataFrame(
        raw_rows
    )


    # =====================================================
    # Summary
    # =====================================================

    summary_rows = []


    for rep, group in (
        raw.groupby(
            "representation"
        )
    ):

        n = len(group)

        if n == 0:
            continue


        summary_rows.append({

            "representation":
                rep,

            "queries":
                n,

            "top1_unique_correct_rate":
                float(
                    group[
                        "top1_unique_correct"
                    ].mean()
                ),

            "top1_true_in_tie_rate":
                float(
                    group[
                        "top1_true_in_tie"
                    ].mean()
                ),

            "top3_parent_recall":
                float(
                    group[
                        "top3_true"
                    ].mean()
                ),

            "top5_parent_recall":
                float(
                    group[
                        "top5_true"
                    ].mean()
                ),

            "top10_parent_recall":
                float(
                    group[
                        "top10_true"
                    ].mean()
                ),

            "mrr_optimistic":
                float(
                    (
                        1.0
                        /
                        group[
                            "optimistic_rank"
                        ]
                    ).mean()
                ),

            "mean_best_distance":
                float(
                    group[
                        "best_distance"
                    ].mean()
                ),

            "mean_true_distance":
                float(
                    group[
                        "true_distance"
                    ].mean()
                ),

            "mean_top1_margin":
                float(
                    group[
                        "top1_margin"
                    ].mean()
                ),

            "best_tie_rate":
                float(
                    (
                        group[
                            "best_tie_size"
                        ]
                        > 1
                    ).mean()
                ),
        })


    summary_df = pd.DataFrame(
        summary_rows
    )


    summary_df = (
        summary_df.sort_values(

            "top1_unique_correct_rate",

            ascending=False
        )
    )


    # =====================================================
    # Phase 3C reference
    # =====================================================

    reference_naive = None

    phase3c = (
        RESULT_ROOT
        / "phase3c_summary.json"
    )


    if phase3c.exists():

        try:

            data = json.loads(
                phase3c.read_text(
                    encoding="utf-8-sig"
                )
            )

            code = (
                data
                .get(
                    "by_modality",
                    {}
                )
                .get(
                    "CODE_BINARY"
                )
            )


            if code:

                reference_naive = {

                    "queries":
                        int(
                            code.get(
                                "components",
                                0
                            )
                        ),

                    "top1_unique_correct_rate":
                        float(
                            code.get(
                                "unique_correct_rate",
                                0.0
                            )
                        ),

                    "top1_true_in_tie_rate":
                        float(
                            code.get(
                                "true_in_best_tie_rate",
                                0.0
                            )
                        ),
                }

        except Exception:
            pass


    summary = {

        "path_failed_code_queries":
            len(hard),

        "historical_queries_disassembled":
            len(query_records),

        "current_disassembly_failures":
            len(current_failures),

        "historical_disassembly_failures":
            len(historical_failures),

        "reference_naive_binary_token_simhash":
            reference_naive,

        "bytecode_representations": {},
    }


    for _, row in (
        summary_df.iterrows()
    ):

        rep = (
            row["representation"]
        )

        summary[
            "bytecode_representations"
        ][rep] = {

            "queries":
                int(
                    row["queries"]
                ),

            "top1_unique_correct_rate":
                float(
                    row[
                        "top1_unique_correct_rate"
                    ]
                ),

            "top1_true_in_tie_rate":
                float(
                    row[
                        "top1_true_in_tie_rate"
                    ]
                ),

            "top3_parent_recall":
                float(
                    row[
                        "top3_parent_recall"
                    ]
                ),

            "top5_parent_recall":
                float(
                    row[
                        "top5_parent_recall"
                    ]
                ),

            "top10_parent_recall":
                float(
                    row[
                        "top10_parent_recall"
                    ]
                ),

            "mrr_optimistic":
                float(
                    row[
                        "mrr_optimistic"
                    ]
                ),

            "mean_best_distance":
                float(
                    row[
                        "mean_best_distance"
                    ]
                ),

            "mean_true_distance":
                float(
                    row[
                        "mean_true_distance"
                    ]
                ),

            "mean_top1_margin":
                float(
                    row[
                        "mean_top1_margin"
                    ]
                ),

            "best_tie_rate":
                float(
                    row[
                        "best_tie_rate"
                    ]
                ),
        }


    # =====================================================
    # Save
    # =====================================================

    raw.to_csv(

        RESULT_ROOT
        / "bytecode_baseline_raw.csv",

        index=False,
        encoding="utf-8-sig",
    )


    summary_df.to_csv(

        RESULT_ROOT
        / "bytecode_baseline_summary.csv",

        index=False,
        encoding="utf-8-sig",
    )


    pd.DataFrame(
        current_failures
    ).to_csv(

        RESULT_ROOT
        / "phase3d_current_failures.csv",

        index=False,
        encoding="utf-8-sig",
    )


    pd.DataFrame(
        historical_failures
    ).to_csv(

        RESULT_ROOT
        / "phase3d_historical_failures.csv",

        index=False,
        encoding="utf-8-sig",
    )


    (
        RESULT_ROOT
        / "phase3d_summary.json"
    ).write_text(

        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8",
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

    print()

    print(
        "Summary CSV: "
        "results\\bytecode_baseline_summary.csv"
    )

    print(
        "Raw CSV    : "
        "results\\bytecode_baseline_raw.csv"
    )


if __name__ == "__main__":
    main()