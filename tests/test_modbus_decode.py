import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modbus_decode import decode_registers


def test_decode_uint16_big_big():
    assert decode_registers([0x1234, 0xABCD], "uint16", byte_order="big", word_order="big") == [0x1234, 0xABCD]


def test_decode_int16_negative_one():
    assert decode_registers([0xFFFF], "int16") == [-1]


def test_decode_uint32_big_big():
    assert decode_registers([0x1122, 0x3344], "uint32", byte_order="big", word_order="big") == [0x11223344]


def test_decode_uint32_word_swap():
    assert decode_registers([0x1122, 0x3344], "uint32", byte_order="big", word_order="little") == [0x33441122]


def test_decode_float32_one():
    values = decode_registers([0x3F80, 0x0000], "float32", byte_order="big", word_order="big")
    assert values[0] == pytest.approx(1.0)


def test_decode_invalid_count_raises():
    with pytest.raises(ValueError):
        decode_registers([0x0001], "uint32")

