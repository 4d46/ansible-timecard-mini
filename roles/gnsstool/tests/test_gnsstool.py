"""
Encoding tests for gnsstool's UBX configuration messages.

These pin the exact bytes sent to the chip. A wrong key ID or checksum is
silently discarded by the receiver, so it would otherwise only show up as
"setting didn't take" on real hardware.

Run: python3 -m unittest discover -s roles/gnsstool/tests
"""

import struct
import sys
import types
import unittest
from pathlib import Path

# gnsstool imports smbus2 at module load; it isn't needed to build or parse messages
sys.modules.setdefault('smbus2', types.ModuleType('smbus2'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'files'))

import gnsstool  # noqa: E402

RAM = 0x01


def valset_frame(key_id, value):
    payload = gnsstool._valset_payload(key_id, value, RAM)
    return gnsstool._build_ubx(*gnsstool.CFG_VALSET, payload)


def valget_response(key_id, value_bytes):
    return struct.pack('<BBH', 1, 0, 0) + struct.pack('<I', key_id) + value_bytes


class ValsetFrameTest(unittest.TestCase):
    def test_stationary_dynmodel_frame(self):
        frame = valset_frame(gnsstool.CFG_NAVSPG_DYNMODEL, gnsstool.DYNMODEL_STATIONARY)
        self.assertEqual(frame.hex(' ').upper(),
                         'B5 62 06 8A 09 00 00 01 00 00 21 00 11 20 02 EE 4B')

    def test_min_elevation_15_frame(self):
        frame = valset_frame(gnsstool.CFG_NAVSPG_INFIL_MINELEV, 15)
        self.assertEqual(frame.hex(' ').upper(),
                         'B5 62 06 8A 09 00 00 01 00 00 A4 00 11 20 0F 7E E7')

    def test_min_elevation_negative_is_twos_complement(self):
        # I1 key: -5 must encode as 0xFB, not raise or wrap incorrectly
        payload = gnsstool._valset_payload(gnsstool.CFG_NAVSPG_INFIL_MINELEV, -5, RAM)
        self.assertEqual(payload[-1], 0xFB)


class ValgetParseTest(unittest.TestCase):
    def test_min_elevation_read_as_signed(self):
        data = valget_response(gnsstool.CFG_NAVSPG_INFIL_MINELEV, b'\xfb')
        self.assertEqual(gnsstool._parse_valget(data, gnsstool.CFG_NAVSPG_INFIL_MINELEV), -5)

    def test_dynmodel_read_as_unsigned(self):
        data = valget_response(gnsstool.CFG_NAVSPG_DYNMODEL, b'\x02')
        self.assertEqual(gnsstool._parse_valget(data, gnsstool.CFG_NAVSPG_DYNMODEL), 2)

    def test_skips_other_keys_to_find_requested_one(self):
        data = (valget_response(gnsstool.CFG_NAVSPG_DYNMODEL, b'\x02')
                + struct.pack('<I', gnsstool.CFG_NAVSPG_INFIL_MINELEV) + b'\x0f')
        self.assertEqual(gnsstool._parse_valget(data, gnsstool.CFG_NAVSPG_INFIL_MINELEV), 15)

    def test_missing_key_returns_none(self):
        data = valget_response(gnsstool.CFG_NAVSPG_DYNMODEL, b'\x02')
        self.assertIsNone(gnsstool._parse_valget(data, gnsstool.CFG_NAVSPG_INFIL_MINELEV))


if __name__ == '__main__':
    unittest.main()
