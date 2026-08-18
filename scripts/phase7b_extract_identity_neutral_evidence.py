import hashlib
import io
import json
import math
import re
import struct
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from PIL import Image
except ImportError:
    raise RuntimeError(
        "Pillow is required. Run:\n"
        "python -m pip install pillow"
    )


# =========================================================
# Config
# =========================================================

CURRENT_COMPONENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry_filtered.csv"
)

CURRENT_PACKAGE_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_package_registry.csv"
)

SPLIT_CSV = Path(
    "results/"
    "phase6c_project_split.csv"
)

QUERY_PRIVATE_CSV = Path(
    "results/"
    "phase6l_materialized_private_manifest.csv"
)

BENCHMARK_ROOT = Path(
    "data/"
    "final_benchmark"
)


OUTPUT_GALLERY_CSV = Path(
    "results/"
    "phase7b_gallery_identity_neutral_evidence.csv"
)

OUTPUT_QUERY_CSV = Path(
    "results/"
    "phase7b_query_identity_neutral_evidence.csv"
)

OUTPUT_FAILURE_JSON = Path(
    "results/"
    "phase7b_evidence_failures.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase7b_evidence_summary.json"
)


ALLOWED_GALLERY_SPLITS = {
    "CALIBRATION_KNOWN",
    "CALIBRATION_BACKGROUND",
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}


EXPECTED_QUERY_COMPONENTS = 3780

MAX_FEATURE_TOKENS = 100000


# =========================================================
# Helpers
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def normalize_path(value):

    return (
        clean_text(value)
        .replace("\\", "/")
    )


def stable_sha256_bytes(data):

    return hashlib.sha256(
        data
    ).hexdigest()


def log_bucket(value):

    value = int(
        max(
            0,
            value,
        )
    )

    if value == 0:
        return 0

    return int(
        math.log2(
            value
        )
    ) + 1


# =========================================================
# 128-bit SimHash
# =========================================================

def simhash128(tokens):

    if not tokens:
        return ""


    counter = Counter(
        tokens[
            :MAX_FEATURE_TOKENS
        ]
    )


    vector = [
        0
        for _ in range(
            128
        )
    ]


    for token, weight in (
        counter.items()
    ):

        digest = hashlib.sha256(
            str(token).encode(
                "utf-8",
                errors="replace",
            )
        ).digest()


        # First 128 bits.
        value = int.from_bytes(
            digest[:16],
            byteorder="big",
            signed=False,
        )


        for bit in range(
            128
        ):

            mask = (
                1
                <<
                (
                    127
                    - bit
                )
            )


            if value & mask:
                vector[bit] += weight
            else:
                vector[bit] -= weight


    result = 0


    for score in vector:

        result <<= 1

        if score >= 0:
            result |= 1


    return f"{result:032x}"


# =========================================================
# Java class reader
# =========================================================

def read_u1(data, offset):

    if offset + 1 > len(data):
        raise ValueError(
            "unexpected EOF: u1"
        )

    return (
        data[offset],
        offset + 1,
    )


def read_u2(data, offset):

    if offset + 2 > len(data):
        raise ValueError(
            "unexpected EOF: u2"
        )

    value = struct.unpack_from(
        ">H",
        data,
        offset,
    )[0]

    return (
        value,
        offset + 2,
    )


def read_u4(data, offset):

    if offset + 4 > len(data):
        raise ValueError(
            "unexpected EOF: u4"
        )

    value = struct.unpack_from(
        ">I",
        data,
        offset,
    )[0]

    return (
        value,
        offset + 4,
    )


def skip_bytes(
    data,
    offset,
    length,
):

    new_offset = (
        offset
        + int(length)
    )

    if new_offset > len(data):
        raise ValueError(
            "unexpected EOF while skipping"
        )

    return new_offset


def parse_constant_pool(
    data,
    offset,
):

    cp_count, offset = read_u2(
        data,
        offset,
    )


    cp_utf8 = {}


    index = 1


    while index < cp_count:

        tag, offset = read_u1(
            data,
            offset,
        )


        if tag == 1:

            length, offset = read_u2(
                data,
                offset,
            )

            if (
                offset + length
                > len(data)
            ):

                raise ValueError(
                    "invalid UTF8 length"
                )


            raw = data[
                offset:
                offset + length
            ]

            offset += length


            cp_utf8[index] = raw.decode(
                "utf-8",
                errors="replace",
            )


        elif tag in {
            3,
            4,
        }:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        elif tag in {
            5,
            6,
        }:

            offset = skip_bytes(
                data,
                offset,
                8,
            )

            index += 1


        elif tag in {
            7,
            8,
            16,
            19,
            20,
        }:

            offset = skip_bytes(
                data,
                offset,
                2,
            )


        elif tag in {
            9,
            10,
            11,
            12,
            17,
            18,
        }:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        elif tag == 15:

            offset = skip_bytes(
                data,
                offset,
                3,
            )


        else:

            raise ValueError(
                f"unknown constant-pool tag: {tag}"
            )


        index += 1


    return (
        cp_utf8,
        offset,
    )


def skip_member_info(
    data,
    offset,
):

    # access_flags
    _, offset = read_u2(
        data,
        offset,
    )

    # name_index
    _, offset = read_u2(
        data,
        offset,
    )

    # descriptor_index
    _, offset = read_u2(
        data,
        offset,
    )

    attribute_count, offset = read_u2(
        data,
        offset,
    )


    for _ in range(
        attribute_count
    ):

        # attribute_name_index
        _, offset = read_u2(
            data,
            offset,
        )

        length, offset = read_u4(
            data,
            offset,
        )

        offset = skip_bytes(
            data,
            offset,
            length,
        )


    return offset


# =========================================================
# JVM opcode parsing
#
# Only opcode identity is retained.
# Operands are discarded so constant-pool names,
# class names, methods, strings and resource identifiers
# do not become provenance evidence.
# =========================================================

FIXED_OPERANDS = {}


def register_operands(
    opcodes,
    length,
):

    for opcode in opcodes:
        FIXED_OPERANDS[
            opcode
        ] = length


register_operands(
    [0x10],
    1,
)

register_operands(
    [0x11],
    2,
)

register_operands(
    [0x12],
    1,
)

register_operands(
    [
        0x13,
        0x14,
    ],
    2,
)

register_operands(
    list(
        range(
            0x15,
            0x1A,
        )
    ),
    1,
)

register_operands(
    list(
        range(
            0x36,
            0x3B,
        )
    ),
    1,
)

register_operands(
    [0x84],
    2,
)

register_operands(
    list(
        range(
            0x99,
            0xA9,
        )
    ),
    2,
)

register_operands(
    [0xA9],
    1,
)

register_operands(
    list(
        range(
            0xB2,
            0xB9,
        )
    ),
    2,
)

register_operands(
    [
        0xB9,
        0xBA,
    ],
    4,
)

register_operands(
    [
        0xBB,
        0xBD,
        0xC0,
        0xC1,
    ],
    2,
)

register_operands(
    [0xBC],
    1,
)

register_operands(
    [0xC5],
    3,
)

register_operands(
    [
        0xC6,
        0xC7,
    ],
    2,
)

register_operands(
    [
        0xC8,
        0xC9,
    ],
    4,
)


def decode_opcodes(code):

    opcodes = []

    pc = 0

    length = len(
        code
    )


    while pc < length:

        opcode_position = pc

        opcode = code[
            pc
        ]

        opcodes.append(
            opcode
        )

        pc += 1


        # tableswitch
        if opcode == 0xAA:

            while (
                pc % 4
                != 0
            ):

                pc += 1


            if pc + 12 > length:
                break


            default_offset = struct.unpack_from(
                ">i",
                code,
                pc,
            )[0]

            low = struct.unpack_from(
                ">i",
                code,
                pc + 4,
            )[0]

            high = struct.unpack_from(
                ">i",
                code,
                pc + 8,
            )[0]


            _ = default_offset


            pc += 12


            count = (
                high
                - low
                + 1
            )


            if count < 0:
                break


            pc += (
                4
                * count
            )


        # lookupswitch
        elif opcode == 0xAB:

            while (
                pc % 4
                != 0
            ):

                pc += 1


            if pc + 8 > length:
                break


            default_offset = struct.unpack_from(
                ">i",
                code,
                pc,
            )[0]

            npairs = struct.unpack_from(
                ">i",
                code,
                pc + 4,
            )[0]


            _ = default_offset


            pc += 8


            if npairs < 0:
                break


            pc += (
                8
                * npairs
            )


        # wide
        elif opcode == 0xC4:

            if pc >= length:
                break


            modified_opcode = (
                code[
                    pc
                ]
            )


            # wide + modified opcode
            # + index(u2)
            # + const(u2) if iinc
            if modified_opcode == 0x84:

                pc += 5

            else:

                pc += 3


        else:

            pc += int(
                FIXED_OPERANDS.get(
                    opcode,
                    0,
                )
            )


        if pc > length:

            # Malformed/truncated instruction.
            # Do not use partial operand bytes as opcodes.
            break


        if pc <= opcode_position:

            raise RuntimeError(
                "Opcode parser made no progress"
            )


    return opcodes


# =========================================================
# Opcode semantic categories
# =========================================================

def opcode_category(opcode):

    if opcode <= 0x14:
        return "CONST"

    if 0x15 <= opcode <= 0x35:
        return "LOAD"

    if 0x36 <= opcode <= 0x56:
        return "STORE"

    if 0x57 <= opcode <= 0x5F:
        return "STACK"

    if 0x60 <= opcode <= 0x83:
        return "ARITH"

    if opcode == 0x84:
        return "ARITH"

    if 0x85 <= opcode <= 0x93:
        return "CONVERT"

    if 0x94 <= opcode <= 0x98:
        return "COMPARE"

    if 0x99 <= opcode <= 0xA9:
        return "BRANCH"

    if opcode in {
        0xAA,
        0xAB,
        0xC6,
        0xC7,
        0xC8,
        0xC9,
    }:
        return "BRANCH"

    if 0xAC <= opcode <= 0xB1:
        return "RETURN"

    if 0xB2 <= opcode <= 0xB5:
        return "FIELD"

    if 0xB6 <= opcode <= 0xBA:
        return "INVOKE"

    if 0xBB <= opcode <= 0xC5:
        return "OBJECT"

    if opcode in {
        0xC2,
        0xC3,
    }:
        return "MONITOR"

    return "MISC"


# =========================================================
# Parse class methods
# =========================================================

def parse_class_methods(data):

    offset = 0


    magic, offset = read_u4(
        data,
        offset,
    )


    if magic != 0xCAFEBABE:

        raise ValueError(
            "invalid class magic"
        )


    # minor
    _, offset = read_u2(
        data,
        offset,
    )

    # major
    major_version, offset = read_u2(
        data,
        offset,
    )


    cp_utf8, offset = (
        parse_constant_pool(
            data,
            offset,
        )
    )


    # class access
    class_access, offset = read_u2(
        data,
        offset,
    )

    # this_class
    _, offset = read_u2(
        data,
        offset,
    )

    # super_class
    _, offset = read_u2(
        data,
        offset,
    )


    interface_count, offset = read_u2(
        data,
        offset,
    )


    offset = skip_bytes(
        data,
        offset,
        interface_count * 2,
    )


    field_count, offset = read_u2(
        data,
        offset,
    )


    for _ in range(
        field_count
    ):

        offset = skip_member_info(
            data,
            offset,
        )


    method_count, offset = read_u2(
        data,
        offset,
    )


    methods = []


    for _ in range(
        method_count
    ):

        access_flags, offset = read_u2(
            data,
            offset,
        )

        # We deliberately read but NEVER use method name
        # or descriptor as a content feature.
        name_index, offset = read_u2(
            data,
            offset,
        )

        descriptor_index, offset = read_u2(
            data,
            offset,
        )


        _ = name_index
        _ = descriptor_index


        attribute_count, offset = read_u2(
            data,
            offset,
        )


        method_record = {
            "access_flags":
                int(
                    access_flags
                ),

            "max_stack":
                0,

            "max_locals":
                0,

            "opcodes":
                [],
        }


        for _ in range(
            attribute_count
        ):

            attribute_name_index, offset = read_u2(
                data,
                offset,
            )

            attribute_length, offset = read_u4(
                data,
                offset,
            )


            attribute_start = offset

            attribute_end = (
                attribute_start
                + attribute_length
            )


            if attribute_end > len(data):

                raise ValueError(
                    "method attribute exceeds class size"
                )


            attribute_name = (
                cp_utf8.get(
                    attribute_name_index,
                    "",
                )
            )


            if attribute_name == "Code":

                code_offset = (
                    attribute_start
                )


                max_stack, code_offset = read_u2(
                    data,
                    code_offset,
                )

                max_locals, code_offset = read_u2(
                    data,
                    code_offset,
                )

                code_length, code_offset = read_u4(
                    data,
                    code_offset,
                )


                if (
                    code_offset
                    + code_length
                    > attribute_end
                ):

                    raise ValueError(
                        "Code attribute exceeds boundary"
                    )


                code_bytes = data[
                    code_offset:
                    code_offset
                    + code_length
                ]


                method_record[
                    "max_stack"
                ] = int(
                    max_stack
                )

                method_record[
                    "max_locals"
                ] = int(
                    max_locals
                )

                method_record[
                    "opcodes"
                ] = decode_opcodes(
                    code_bytes
                )


            offset = (
                attribute_end
            )


        methods.append(
            method_record
        )


    return {
        "major_version":
            int(
                major_version
            ),

        "class_access":
            int(
                class_access
            ),

        "field_count":
            int(
                field_count
            ),

        "methods":
            methods,
    }


# =========================================================
# CODE_BINARY features
# =========================================================

def extract_code_features(data):

    parsed = parse_class_methods(
        data
    )


    methods = parsed[
        "methods"
    ]


    op3_tokens = []

    struct_tokens = []

    context_tokens = []


    instruction_count = 0

    code_method_count = 0


    for method in methods:

        opcodes = method[
            "opcodes"
        ]

        instruction_count += len(
            opcodes
        )


        if opcodes:

            code_method_count += 1


        # -------------------------------------------------
        # Representation 1: opcode 3-grams
        # -------------------------------------------------

        if len(opcodes) < 3:

            if opcodes:

                op3_tokens.append(
                    "SHORT_"
                    +
                    "_".join(
                        f"{opcode:02x}"
                        for opcode
                        in opcodes
                    )
                )

            else:

                op3_tokens.append(
                    "EMPTY_METHOD"
                )

        else:

            for index in range(
                len(opcodes) - 2
            ):

                op3_tokens.append(
                    (
                        f"{opcodes[index]:02x}-"
                        f"{opcodes[index + 1]:02x}-"
                        f"{opcodes[index + 2]:02x}"
                    )
                )


        # -------------------------------------------------
        # Representation 2: structural method summary
        # -------------------------------------------------

        struct_tokens.append(
            "METHOD_LEN_"
            + str(
                log_bucket(
                    len(opcodes)
                )
            )
        )

        struct_tokens.append(
            "METHOD_STACK_"
            + str(
                log_bucket(
                    method[
                        "max_stack"
                    ]
                )
            )
        )

        struct_tokens.append(
            "METHOD_LOCALS_"
            + str(
                log_bucket(
                    method[
                        "max_locals"
                    ]
                )
            )
        )


        flags = int(
            method[
                "access_flags"
            ]
        )


        if flags & 0x0008:
            struct_tokens.append(
                "METHOD_STATIC"
            )

        if flags & 0x0020:
            struct_tokens.append(
                "METHOD_SYNCHRONIZED"
            )

        if flags & 0x0100:
            struct_tokens.append(
                "METHOD_NATIVE"
            )

        if flags & 0x0400:
            struct_tokens.append(
                "METHOD_ABSTRACT"
            )


        category_counts = Counter(
            opcode_category(
                opcode
            )
            for opcode
            in opcodes
        )


        for category in sorted(
            category_counts
        ):

            struct_tokens.append(
                (
                    "CAT_"
                    + category
                    + "_"
                    + str(
                        log_bucket(
                            category_counts[
                                category
                            ]
                        )
                    )
                )
            )


        # -------------------------------------------------
        # Representation 3: semantic-context n-grams
        # -------------------------------------------------

        categories = [
            opcode_category(
                opcode
            )
            for opcode
            in opcodes
        ]


        if len(categories) < 3:

            if categories:

                context_tokens.append(
                    "CTX_SHORT_"
                    +
                    "_".join(
                        categories
                    )
                )

            else:

                context_tokens.append(
                    "CTX_EMPTY"
                )

        else:

            for index in range(
                len(categories) - 2
            ):

                context_tokens.append(
                    (
                        categories[index]
                        + "-"
                        + categories[
                            index + 1
                        ]
                        + "-"
                        + categories[
                            index + 2
                        ]
                    )
                )


    # Class-level structural features.
    struct_tokens.extend(
        [
            "CLASS_METHODS_"
            + str(
                log_bucket(
                    len(methods)
                )
            ),

            "CLASS_CODE_METHODS_"
            + str(
                log_bucket(
                    code_method_count
                )
            ),

            "CLASS_FIELDS_"
            + str(
                log_bucket(
                    parsed[
                        "field_count"
                    ]
                )
            ),

            "CLASS_INSTRUCTIONS_"
            + str(
                log_bucket(
                    instruction_count
                )
            ),
        ]
    )


    return {
        "code_op3_simhash128":
            simhash128(
                op3_tokens
            ),

        "code_struct_simhash128":
            simhash128(
                struct_tokens
            ),

        "code_context_simhash128":
            simhash128(
                context_tokens
            ),

        "code_method_count":
            int(
                len(methods)
            ),

        "code_instruction_count":
            int(
                instruction_count
            ),

        "code_major_version":
            int(
                parsed[
                    "major_version"
                ]
            ),
    }


# =========================================================
# STRUCTURED normalization
# =========================================================

COMMON_KEYS = {
    "type",
    "parent",
    "textures",
    "texture",
    "model",
    "item",
    "items",
    "ingredient",
    "ingredients",
    "result",
    "results",
    "count",
    "conditions",
    "condition",
    "values",
    "value",
    "replace",
    "entries",
    "entry",
    "pools",
    "pool",
    "rolls",
    "functions",
    "function",
    "name",
    "weight",
    "quality",
    "predicate",
    "display",
    "elements",
    "faces",
    "variants",
    "multipart",
    "apply",
    "when",
    "loader",
    "providers",
    "provider",
    "feature",
    "placement",
    "biomes",
    "biome",
    "category",
    "group",
    "pattern",
    "key",
    "criteria",
    "requirements",
    "rewards",
    "recipes",
    "advancements",
    "sounds",
    "subtitle",
    "min",
    "max",
    "chance",
    "levels",
    "level",
    "tag",
    "id",
}


RESOURCE_ID_RE = re.compile(
    r"^[A-Za-z0-9_.-]+:"
    r"[A-Za-z0-9_./-]+$"
)

URL_RE = re.compile(
    r"^(https?|ftp)://",
    re.IGNORECASE,
)

HEX_RE = re.compile(
    r"^[0-9a-fA-F]{16,}$"
)

QUALIFIED_ID_RE = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]*"
    r"([./][A-Za-z_$][A-Za-z0-9_$]*){2,}$"
)


def string_shape(value):

    text = str(
        value
    )

    stripped = (
        text.strip()
    )


    tokens = [
        "STR_LEN_"
        + str(
            log_bucket(
                len(stripped)
            )
        )
    ]


    if not stripped:

        tokens.append(
            "STR_EMPTY"
        )

        return tokens


    if URL_RE.match(
        stripped
    ):

        tokens.append(
            "STR_URL"
        )

        return tokens


    if HEX_RE.match(
        stripped
    ):

        tokens.append(
            "STR_HEX"
        )

        return tokens


    if RESOURCE_ID_RE.match(
        stripped
    ):

        namespace, resource_path = (
            stripped.split(
                ":",
                1,
            )
        )


        namespace_lower = (
            namespace.lower()
        )


        if namespace_lower in {
            "minecraft",
            "c",
        }:

            tokens.append(
                "RID_EXTERNAL_"
                + namespace_lower
            )

        else:

            # Never expose literal MOD namespace.
            tokens.append(
                "RID_NONSTANDARD_NAMESPACE"
            )


        path_parts = [
            part
            for part
            in resource_path.split(
                "/"
            )
            if part
        ]


        tokens.append(
            "RID_DEPTH_"
            + str(
                log_bucket(
                    len(
                        path_parts
                    )
                )
            )
        )


        for part in path_parts[
            :8
        ]:

            tokens.append(
                "RID_PART_LEN_"
                + str(
                    log_bucket(
                        len(part)
                    )
                )
            )


        return tokens


    if QUALIFIED_ID_RE.match(
        stripped
    ):

        tokens.append(
            "STR_QUALIFIED_IDENTIFIER"
        )

        return tokens


    if any(
        char.isspace()
        for char in stripped
    ):

        tokens.append(
            "STR_HAS_SPACE"
        )


    if stripped.isdigit():

        tokens.append(
            "STR_INTEGER_TEXT"
        )


    elif re.fullmatch(
        r"[-+]?\d+(\.\d+)?",
        stripped,
    ):

        tokens.append(
            "STR_NUMBER_TEXT"
        )


    elif stripped.isalpha():

        tokens.append(
            "STR_ALPHA"
        )


    elif stripped.isalnum():

        tokens.append(
            "STR_ALNUM"
        )


    else:

        tokens.append(
            "STR_MIXED"
        )


    word_count = len(
        re.findall(
            r"\w+",
            stripped,
        )
    )


    tokens.append(
        "STR_WORDS_"
        + str(
            log_bucket(
                word_count
            )
        )
    )


    return tokens


def key_token(key):

    key_text = (
        str(key)
        .strip()
        .lower()
    )


    if key_text in COMMON_KEYS:

        return (
            "KEY_COMMON_"
            + key_text
        )


    return (
        "KEY_OTHER_LEN_"
        + str(
            log_bucket(
                len(
                    key_text
                )
            )
        )
    )


def json_structure_tokens(
    value,
):

    tokens = []


    def emit(token):

        if (
            len(tokens)
            < MAX_FEATURE_TOKENS
        ):

            tokens.append(
                token
            )


    def walk(node):

        if (
            len(tokens)
            >= MAX_FEATURE_TOKENS
        ):
            return


        if node is None:

            emit(
                "NULL"
            )


        elif isinstance(
            node,
            bool,
        ):

            emit(
                "BOOL"
            )


        elif isinstance(
            node,
            int,
        ) and not isinstance(
            node,
            bool,
        ):

            emit(
                "INT_MAG_"
                + str(
                    log_bucket(
                        abs(node)
                    )
                )
            )


        elif isinstance(
            node,
            float,
        ):

            if math.isfinite(
                node
            ):

                emit(
                    "FLOAT_MAG_"
                    + str(
                        log_bucket(
                            int(
                                abs(node)
                            )
                        )
                    )
                )

            else:

                emit(
                    "FLOAT_SPECIAL"
                )


        elif isinstance(
            node,
            str,
        ):

            for token in string_shape(
                node
            ):

                emit(
                    token
                )


        elif isinstance(
            node,
            list,
        ):

            emit(
                "ARR_LEN_"
                + str(
                    log_bucket(
                        len(node)
                    )
                )
            )


            for child in node:

                walk(
                    child
                )


        elif isinstance(
            node,
            dict,
        ):

            emit(
                "OBJ_LEN_"
                + str(
                    log_bucket(
                        len(node)
                    )
                )
            )


            # Sort only by normalized key token.
            # Literal key identity is not retained.
            items = [
                (
                    key_token(
                        key
                    ),
                    child,
                )
                for key, child
                in node.items()
            ]


            items.sort(
                key=lambda item: item[0]
            )


            for normalized_key, child in (
                items
            ):

                emit(
                    normalized_key
                )

                walk(
                    child
                )


        else:

            emit(
                "OTHER"
            )


    walk(
        value
    )


    return tokens


def fallback_structured_tokens(
    text,
):

    raw_tokens = re.findall(
        r"""
        [A-Za-z_][A-Za-z0-9_.:/-]*
        |
        [-+]?\d+(?:\.\d+)?
        |
        [{}\[\](),:=]
        """,
        text,
        flags=re.VERBOSE,
    )


    normalized = []


    for token in raw_tokens[
        :MAX_FEATURE_TOKENS
    ]:

        if token in {
            "{",
            "}",
            "[",
            "]",
            "(",
            ")",
            ",",
            ":",
            "=",
        }:

            normalized.append(
                "PUNC_"
                + token
            )

            continue


        if re.fullmatch(
            r"[-+]?\d+(?:\.\d+)?",
            token,
        ):

            normalized.append(
                "NUMBER"
            )

            continue


        if RESOURCE_ID_RE.match(
            token
        ):

            normalized.extend(
                string_shape(
                    token
                )
            )

            continue


        lower = (
            token.lower()
        )


        if lower in COMMON_KEYS:

            normalized.append(
                "WORD_COMMON_"
                + lower
            )

        else:

            normalized.append(
                "WORD_LEN_"
                + str(
                    log_bucket(
                        len(token)
                    )
                )
            )


    return normalized


def extract_structured_features(data):

    text = data.decode(
        "utf-8-sig",
        errors="replace",
    )


    stripped = (
        text.lstrip()
    )


    parse_kind = (
        "TEXT_FALLBACK"
    )


    tokens = None


    if stripped.startswith(
        "{"
    ) or stripped.startswith(
        "["
    ):

        try:

            parsed = json.loads(
                text
            )

            tokens = (
                json_structure_tokens(
                    parsed
                )
            )

            parse_kind = (
                "JSON"
            )

        except Exception:

            tokens = None


    if tokens is None:

        tokens = (
            fallback_structured_tokens(
                text
            )
        )


    # Add local token 3-grams to preserve structure while
    # retaining only normalized token identities.
    grams = []


    for index in range(
        max(
            0,
            len(tokens) - 2,
        )
    ):

        grams.append(
            (
                tokens[index]
                + "|"
                + tokens[index + 1]
                + "|"
                + tokens[index + 2]
            )
        )


        if (
            len(grams)
            >= MAX_FEATURE_TOKENS
        ):

            break


    combined = (
        tokens
        +
        grams
    )


    return {
        "structured_simhash128":
            simhash128(
                combined
            ),

        "structured_token_count":
            int(
                len(tokens)
            ),

        "structured_parse_kind":
            parse_kind,
    }


# =========================================================
# IMAGE features
# =========================================================

DCT_N = 32


def build_dct_matrix(n):

    matrix = np.zeros(
        (
            n,
            n,
        ),
        dtype=np.float64,
    )


    for k in range(n):

        alpha = (
            math.sqrt(
                1.0 / n
            )
            if k == 0
            else
            math.sqrt(
                2.0 / n
            )
        )


        for i in range(n):

            matrix[
                k,
                i
            ] = (
                alpha
                *
                math.cos(
                    (
                        math.pi
                        *
                        (
                            2 * i + 1
                        )
                        *
                        k
                    )
                    /
                    (
                        2 * n
                    )
                )
            )


    return matrix


DCT_MATRIX = build_dct_matrix(
    DCT_N
)


try:
    RESAMPLE_LANCZOS = (
        Image.Resampling.LANCZOS
    )
except AttributeError:
    RESAMPLE_LANCZOS = (
        Image.LANCZOS
    )


def bits_to_hex(bits):

    value = 0


    for bit in bits:

        value <<= 1

        if bit:
            value |= 1


    width = (
        len(bits)
        // 4
    )


    return (
        f"{value:0{width}x}"
    )


def image_ahash64(gray):

    resized = gray.resize(
        (
            8,
            8,
        ),
        RESAMPLE_LANCZOS,
    )


    values = np.asarray(
        resized,
        dtype=np.float64,
    ).reshape(
        -1
    )


    threshold = float(
        values.mean()
    )


    bits = [
        bool(
            value
            >= threshold
        )
        for value in values
    ]


    return bits_to_hex(
        bits
    )


def image_dhash64(gray):

    resized = gray.resize(
        (
            9,
            8,
        ),
        RESAMPLE_LANCZOS,
    )


    values = np.asarray(
        resized,
        dtype=np.int16,
    )


    bits = []


    for y in range(8):

        for x in range(8):

            bits.append(
                bool(
                    values[
                        y,
                        x
                    ]
                    >
                    values[
                        y,
                        x + 1
                    ]
                )
            )


    return bits_to_hex(
        bits
    )


def image_phash64(gray):

    resized = gray.resize(
        (
            DCT_N,
            DCT_N,
        ),
        RESAMPLE_LANCZOS,
    )


    values = np.asarray(
        resized,
        dtype=np.float64,
    )


    dct = (
        DCT_MATRIX
        @ values
        @ DCT_MATRIX.T
    )


    low = (
        dct[
            :8,
            :8
        ]
        .reshape(
            -1
        )
    )


    median = float(
        np.median(
            low[
                1:
            ]
        )
    )


    bits = [
        False
    ]


    for value in low[
        1:
    ]:

        bits.append(
            bool(
                value
                >= median
            )
        )


    return bits_to_hex(
        bits
    )


def image_hist16(gray):

    values = np.asarray(
        gray,
        dtype=np.uint8,
    ).reshape(
        -1
    )


    hist, _ = np.histogram(
        values,
        bins=16,
        range=(
            0,
            256,
        ),
    )


    total = int(
        hist.sum()
    )


    if total <= 0:

        normalized = [
            0
            for _ in range(
                16
            )
        ]

    else:

        normalized = [
            int(
                round(
                    (
                        int(value)
                        /
                        total
                    )
                    *
                    10000
                )
            )

            for value in hist
        ]


    return ",".join(
        str(value)
        for value
        in normalized
    )


def extract_image_features(data):

    image = Image.open(
        io.BytesIO(
            data
        )
    )


    frame_count = int(
        getattr(
            image,
            "n_frames",
            1,
        )
    )


    if frame_count > 1:

        image.seek(
            0
        )


    width, height = (
        image.size
    )


    gray = image.convert(
        "L"
    )


    return {
        "image_ahash64":
            image_ahash64(
                gray
            ),

        "image_dhash64":
            image_dhash64(
                gray
            ),

        "image_phash64":
            image_phash64(
                gray
            ),

        "image_hist16":
            image_hist16(
                gray
            ),

        "image_width":
            int(
                width
            ),

        "image_height":
            int(
                height
            ),

        "image_frames":
            frame_count,
    }


# =========================================================
# Unified extractor
# =========================================================

SIGNATURE_COLUMNS = [
    "code_op3_simhash128",
    "code_struct_simhash128",
    "code_context_simhash128",
    "code_method_count",
    "code_instruction_count",
    "code_major_version",
    "structured_simhash128",
    "structured_token_count",
    "structured_parse_kind",
    "image_ahash64",
    "image_dhash64",
    "image_phash64",
    "image_hist16",
    "image_width",
    "image_height",
    "image_frames",
]


def empty_signature_record():

    return {
        column: ""
        for column in (
            SIGNATURE_COLUMNS
        )
    }


def extract_features(
    modality,
    data,
):

    result = (
        empty_signature_record()
    )


    if modality == "CODE_BINARY":

        result.update(
            extract_code_features(
                data
            )
        )


    elif modality == "STRUCTURED":

        result.update(
            extract_structured_features(
                data
            )
        )


    elif modality == "IMAGE":

        result.update(
            extract_image_features(
                data
            )
        )


    else:

        raise ValueError(
            f"Unsupported modality: "
            f"{modality}"
        )


    return result


# =========================================================
# Load registries
# =========================================================

for path in [
    CURRENT_COMPONENT_CSV,
    CURRENT_PACKAGE_CSV,
    SPLIT_CSV,
    QUERY_PRIVATE_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


current_components = pd.read_csv(
    CURRENT_COMPONENT_CSV
)

current_packages = pd.read_csv(
    CURRENT_PACKAGE_CSV
)

splits = pd.read_csv(
    SPLIT_CSV
)

query_private = pd.read_csv(
    QUERY_PRIVATE_CSV
)


for df in [
    current_components,
    current_packages,
    splits,
]:

    if "fresh_id" in df.columns:

        df[
            "fresh_id"
        ] = df[
            "fresh_id"
        ].astype(str)


for df in [
    current_components,
    current_packages,
]:

    if "version_id" in df.columns:

        df[
            "version_id"
        ] = df[
            "version_id"
        ].astype(str)


print(
    "======================================"
)

print(
    "Phase 7B - Identity-Neutral Evidence"
)

print(
    "======================================"
)


# =========================================================
# Split map
# =========================================================

split_map = dict(
    zip(
        splits[
            "fresh_id"
        ].astype(str),

        splits[
            "frozen_split"
        ].astype(str),
    )
)


current_components[
    "frozen_split"
] = current_components[
    "fresh_id"
].map(
    split_map
)


if current_components[
    "frozen_split"
].isna().any():

    raise RuntimeError(
        "Current component without frozen split"
    )


# =========================================================
# Gallery excludes UNKNOWN_HELDOUT completely
# =========================================================

gallery_components = current_components[
    current_components[
        "frozen_split"
    ].isin(
        ALLOWED_GALLERY_SPLITS
    )
].copy()


unknown_gallery_components = current_components[
    current_components[
        "frozen_split"
    ]
    == "UNKNOWN_HELDOUT"
]


print(
    "Gallery components:",
    len(
        gallery_components
    )
)

print(
    "UNKNOWN current components excluded:",
    len(
        unknown_gallery_components
    )
)


# =========================================================
# Current package path column
# =========================================================

package_path_column = None


for candidate in [
    "local_path",
    "jar_path",
    "path",
]:

    if candidate in (
        current_packages.columns
    ):

        package_path_column = (
            candidate
        )

        break


if package_path_column is None:

    raise RuntimeError(
        "Could not find JAR path column in "
        "fresh_current_package_registry.csv. "
        "Expected one of: local_path, jar_path, path"
    )


# =========================================================
# Package maps
# =========================================================

package_by_pair = {}

package_by_project = {}


for row in (
    current_packages.itertuples(
        index=False
    )
):

    fresh_id = clean_text(
        row.fresh_id
    )


    version_id = (
        clean_text(
            getattr(
                row,
                "version_id",
                "",
            )
        )
    )


    jar_path = Path(
        clean_text(
            getattr(
                row,
                package_path_column,
            )
        )
    )


    if version_id:

        package_by_pair[
            (
                fresh_id,
                version_id,
            )
        ] = jar_path


    if fresh_id in package_by_project:

        if (
            package_by_project[
                fresh_id
            ]
            != jar_path
        ):

            # Current registry should have one current JAR
            # per project. Keep pair matching authoritative.
            pass

    else:

        package_by_project[
            fresh_id
        ] = jar_path


# =========================================================
# JAR reader cache
# =========================================================

jar_cache = {}


def read_current_component(
    fresh_id,
    version_id,
    relative_path,
):

    pair_key = (
        fresh_id,
        version_id,
    )


    jar_path = (
        package_by_pair.get(
            pair_key
        )
    )


    if jar_path is None:

        jar_path = (
            package_by_project.get(
                fresh_id
            )
        )


    if jar_path is None:

        raise FileNotFoundError(
            f"No current JAR for "
            f"{fresh_id} {version_id}"
        )


    if not jar_path.exists():

        raise FileNotFoundError(
            f"Current JAR not found: "
            f"{jar_path}"
        )


    jar_key = str(
        jar_path
    )


    if jar_key not in (
        jar_cache
    ):

        jar_cache[
            jar_key
        ] = zipfile.ZipFile(
            jar_path,
            "r",
        )


    return (
        jar_cache[
            jar_key
        ].read(
            normalize_path(
                relative_path
            )
        )
    )


# =========================================================
# Deterministic gallery IDs
# =========================================================

sort_columns = [
    column
    for column in [
        "fresh_id",
        "version_id",
        "modality",
        "component_sha256",
        "relative_path",
    ]
    if column
    in gallery_components.columns
]


gallery_components = (
    gallery_components
    .sort_values(
        sort_columns,
        kind="stable",
    )
    .reset_index(
        drop=True
    )
)


# =========================================================
# Extract gallery evidence
# =========================================================

gallery_rows = []

failure_rows = []


gallery_failure_count = 0

gallery_modality_counts = Counter()


total_gallery = len(
    gallery_components
)


try:

    for index, row in enumerate(
        gallery_components.itertuples(
            index=False
        ),
        start=1,
    ):

        if (
            index == 1
            or
            index % 1000 == 0
        ):

            print(
                f"gallery "
                f"{index}/"
                f"{total_gallery}"
            )


        gallery_id = (
            f"G7B{index:07d}"
        )


        fresh_id = clean_text(
            row.fresh_id
        )

        version_id = clean_text(
            getattr(
                row,
                "version_id",
                "",
            )
        )

        modality = clean_text(
            row.modality
        )

        relative_path = normalize_path(
            row.relative_path
        )


        try:

            raw = read_current_component(
                fresh_id,
                version_id,
                relative_path,
            )


            expected_sha = clean_text(
                row.component_sha256
            )


            actual_sha = (
                stable_sha256_bytes(
                    raw
                )
            )


            if (
                expected_sha
                and
                actual_sha
                != expected_sha
            ):

                raise RuntimeError(
                    "gallery SHA mismatch"
                )


            features = extract_features(
                modality,
                raw,
            )


            gallery_modality_counts[
                modality
            ] += 1


            output_row = {
                "gallery_component_id":
                    gallery_id,

                "fresh_id":
                    fresh_id,

                "frozen_split":
                    clean_text(
                        row.frozen_split
                    ),

                "modality":
                    modality,
            }


            output_row.update(
                features
            )


            gallery_rows.append(
                output_row
            )


        except Exception as exc:

            gallery_failure_count += 1


            failure_rows.append({
                "scope":
                    "GALLERY",

                "identifier":
                    gallery_id,

                "fresh_id":
                    fresh_id,

                "modality":
                    modality,

                "reason":
                    repr(
                        exc
                    ),
            })


# =========================================================
# Close gallery JARs before query extraction
# =========================================================

finally:

    for jar in (
        jar_cache.values()
    ):

        try:
            jar.close()
        except Exception:
            pass


    jar_cache.clear()


# =========================================================
# Extract query evidence
#
# Uses materialized public payload bytes.
# Source path / source identity are not used.
# =========================================================

query_rows = []

query_failure_count = 0

query_modality_counts = Counter()


if len(
    query_private
) != EXPECTED_QUERY_COMPONENTS:

    raise RuntimeError(
        f"Expected {EXPECTED_QUERY_COMPONENTS} "
        f"query components, "
        f"got {len(query_private)}"
    )


query_private = (
    query_private
    .sort_values(
        [
            "query_id",
            "node_id",
        ],
        kind="stable",
    )
    .reset_index(
        drop=True
    )
)


for index, row in enumerate(
    query_private.itertuples(
        index=False
    ),
    start=1,
):

    if (
        index == 1
        or
        index % 250 == 0
    ):

        print(
            f"query "
            f"{index}/"
            f"{len(query_private)}"
        )


    query_id = clean_text(
        row.query_id
    )

    node_id = clean_text(
        row.node_id
    )

    modality = clean_text(
        row.modality
    )


    payload_relpath = clean_text(
        row.payload_relpath
    )


    payload_path = (
        BENCHMARK_ROOT
        /
        payload_relpath
    )


    try:

        if not payload_path.exists():

            raise FileNotFoundError(
                f"Payload not found: "
                f"{payload_path}"
            )


        raw = payload_path.read_bytes()


        features = extract_features(
            modality,
            raw,
        )


        query_modality_counts[
            modality
        ] += 1


        output_row = {
            "query_id":
                query_id,

            "node_id":
                node_id,

            "modality":
                modality,
        }


        output_row.update(
            features
        )


        query_rows.append(
            output_row
        )


    except Exception as exc:

        query_failure_count += 1


        failure_rows.append({
            "scope":
                "QUERY",

            "identifier":
                (
                    query_id
                    + "/"
                    + node_id
                ),

            "fresh_id":
                "",

            "modality":
                modality,

            "reason":
                repr(
                    exc
                ),
        })


# =========================================================
# DataFrames
# =========================================================

gallery_evidence = pd.DataFrame(
    gallery_rows
)

query_evidence = pd.DataFrame(
    query_rows
)


# =========================================================
# Leakage safety
# =========================================================

QUERY_FORBIDDEN_COLUMNS = {
    "fresh_id",
    "source_fresh_id",
    "source_relative_path",
    "relative_path",
    "component_sha256",
    "payload_sha256",
    "ground_truth_label",
    "k_true",
    "scenario",
    "stage",
    "version_id",
    "source_version_id",
}


query_column_set = set(
    query_evidence.columns
)


leaked_query_columns = (
    query_column_set
    &
    QUERY_FORBIDDEN_COLUMNS
)


if leaked_query_columns:

    raise RuntimeError(
        "Query evidence leaked private columns: "
        + str(
            sorted(
                leaked_query_columns
            )
        )
    )


# UNKNOWN current project must never appear in gallery.
unknown_project_ids = set(
    splits[
        splits[
            "frozen_split"
        ]
        == "UNKNOWN_HELDOUT"
    ][
        "fresh_id"
    ].astype(str)
)


gallery_project_ids = set(
    gallery_evidence[
        "fresh_id"
    ].astype(str)
) if len(
    gallery_evidence
) else set()


unknown_leakage = (
    unknown_project_ids
    &
    gallery_project_ids
)


if unknown_leakage:

    raise RuntimeError(
        "UNKNOWN current project leaked into gallery: "
        + str(
            sorted(
                unknown_leakage
            )
        )
    )


# =========================================================
# Save
# =========================================================

OUTPUT_GALLERY_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


gallery_evidence.to_csv(
    OUTPUT_GALLERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


query_evidence.to_csv(
    OUTPUT_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


OUTPUT_FAILURE_JSON.write_text(
    json.dumps(
        failure_rows,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Summary
# =========================================================

gallery_by_split = {}


if len(
    gallery_evidence
):

    for split_name, group in (
        gallery_evidence.groupby(
            "frozen_split"
        )
    ):

        gallery_by_split[
            str(
                split_name
            )
        ] = {
            "components":
                int(
                    len(
                        group
                    )
                ),

            "projects":
                int(
                    group[
                        "fresh_id"
                    ].nunique()
                ),

            "by_modality": {
                str(
                    modality
                ):
                    int(
                        count
                    )

                for modality, count
                in group[
                    "modality"
                ]
                .value_counts()
                .to_dict()
                .items()
            },
        }


summary = {
    "identity_neutral_evidence_extraction_complete":
        True,

    "performance_evaluated":
        False,

    "thresholds_tuned":
        False,

    "representation_policy": {
        "CODE_BINARY": (
            "raw JVM opcode identities and structural "
            "method statistics only; constant-pool "
            "operands, class/package/method names, "
            "descriptors and string literals are not "
            "used as evidence"
        ),

        "STRUCTURED": (
            "normalized structural tokens; file paths "
            "and literal MOD namespaces are not used; "
            "nonstandard resource namespaces are "
            "replaced with generic markers"
        ),

        "IMAGE": (
            "decoded pixel evidence only: aHash, dHash, "
            "pHash and 16-bin luminance histogram"
        ),
    },

    "gallery_input_components":
        int(
            len(
                gallery_components
            )
        ),

    "gallery_evidence_components":
        int(
            len(
                gallery_evidence
            )
        ),

    "query_input_components":
        int(
            len(
                query_private
            )
        ),

    "query_evidence_components":
        int(
            len(
                query_evidence
            )
        ),

    "gallery_failures":
        int(
            gallery_failure_count
        ),

    "query_failures":
        int(
            query_failure_count
        ),

    "failure_records":
        int(
            len(
                failure_rows
            )
        ),

    "gallery_modality_counts": {
        str(key):
            int(value)
        for key, value
        in gallery_modality_counts.items()
    },

    "query_modality_counts": {
        str(key):
            int(value)
        for key, value
        in query_modality_counts.items()
    },

    "gallery_by_split":
        gallery_by_split,

    "unknown_current_projects_extracted_into_gallery":
        int(
            len(
                unknown_leakage
            )
        ),

    "query_private_identity_columns_exposed":
        False,

    "goals_met":
        bool(
            gallery_failure_count
            == 0

            and

            query_failure_count
            == 0

            and

            len(
                query_evidence
            )
            == EXPECTED_QUERY_COMPONENTS

            and

            len(
                unknown_leakage
            )
            == 0
        ),
}


OUTPUT_SUMMARY_JSON.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 7B RESULT"
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
    "Gallery evidence:",
    OUTPUT_GALLERY_CSV
)

print(
    "Query evidence  :",
    OUTPUT_QUERY_CSV
)

print(
    "Failures        :",
    OUTPUT_FAILURE_JSON
)

print(
    "Summary         :",
    OUTPUT_SUMMARY_JSON
)