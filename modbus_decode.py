from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple


DATA_TYPES: Dict[str, Tuple[str, int]] = {
    "uint16": (">H", 1),
    "int16": (">h", 1),
    "uint32": (">I", 2),
    "int32": (">i", 2),
    "float32": (">f", 2),
    "float64": (">d", 4),
}


def registers_per_value(data_type: str) -> int:
    if data_type not in DATA_TYPES:
        raise ValueError(f"Unsupported data type: {data_type}")
    return DATA_TYPES[data_type][1]


def decode_registers(
    registers: List[int],
    data_type: str,
    *,
    byte_order: str = "big",
    word_order: str = "big",
) -> List[Any]:
    if byte_order not in {"big", "little"}:
        raise ValueError(f"Unsupported byte order: {byte_order}")
    if word_order not in {"big", "little"}:
        raise ValueError(f"Unsupported word order: {word_order}")
    if data_type not in DATA_TYPES:
        raise ValueError(f"Unsupported data type: {data_type}")

    fmt, regs_per = DATA_TYPES[data_type]
    if regs_per <= 0:
        raise ValueError("Invalid data type configuration.")

    if len(registers) % regs_per != 0:
        raise ValueError(f"Register count ({len(registers)}) is not a multiple of {regs_per} for {data_type}.")

    decoded: List[Any] = []
    for idx in range(0, len(registers), regs_per):
        chunk = registers[idx : idx + regs_per]

        words = [int(value).to_bytes(2, byteorder="big", signed=False) for value in chunk]
        if byte_order == "little":
            words = [word[::-1] for word in words]

        if word_order == "little" and len(words) > 1:
            words = list(reversed(words))

        payload = b"".join(words)
        decoded.append(struct.unpack(fmt, payload)[0])

    return decoded
