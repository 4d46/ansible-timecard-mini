"""
Encoding tests for gnsstool's UBX configuration messages.

These pin the exact bytes sent to the chip. A wrong key ID or checksum is
silently discarded by the receiver, so it would otherwise only show up as
"setting didn't take" on real hardware.

Run: python3 -m unittest discover -s roles/gnsstool/tests
"""

import contextlib
import io
import re
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

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


def sat(gnss, cno, used=True):
    return dict(gnss=gnss, sv_id=1, cno=cno, elev=45, azim=0, used=used)


class ConstellationSummaryTest(unittest.TestCase):
    def test_counts_only_satellites_with_signal(self):
        # The old SVs column counted cno=0 satellites, so it disagreed with the tracked list
        rows = gnsstool._constellation_summary([sat('GPS', 40), sat('GPS', 0, used=False), sat('GPS', 30)])
        self.assertEqual(rows[0]['tracked'], 2)
        self.assertEqual(rows[0]['avg_snr'], 35.0)

    def test_used_is_separate_from_tracked(self):
        rows = gnsstool._constellation_summary([sat('Galileo', 30), sat('Galileo', 14, used=False)])
        self.assertEqual((rows[0]['tracked'], rows[0]['used']), (2, 1))

    def test_snr_bucket_boundaries(self):
        rows = gnsstool._constellation_summary([sat('GPS', c) for c in (19, 20, 34, 35)])
        self.assertEqual((rows[0]['weak'], rows[0]['fair'], rows[0]['strong']), (1, 2, 1))

    def test_excludes_sbas_and_untracked_constellations(self):
        rows = gnsstool._constellation_summary([sat('SBAS', 40), sat('BeiDou', 0), sat('GPS', 40)])
        self.assertEqual([r['name'] for r in rows], ['GPS'])


class VersionTest(unittest.TestCase):
    def test_includes_build_info_written_at_deploy(self):
        with tempfile.TemporaryDirectory() as d:
            build = Path(d) / 'BUILD'
            build.write_text('commit a1b2c3d-dirty, 2026-10-03\n')
            self.assertEqual(gnsstool.version_string(build),
                             f'gnsstool {gnsstool.__version__} (commit a1b2c3d-dirty, 2026-10-03)')

    def test_missing_build_info_is_reported_not_fatal(self):
        self.assertEqual(gnsstool.version_string(Path('/nonexistent/BUILD')),
                         f'gnsstool {gnsstool.__version__} (build info unavailable)')

    def test_version_matches_changelog(self):
        changelog = (Path(gnsstool.__file__).with_name('CHANGELOG.md')).read_text()
        latest = re.search(r'^## \[(\d+\.\d+\.\d+)\]', changelog, re.MULTILINE).group(1)
        self.assertEqual(gnsstool.__version__, latest)


def run_cli(*argv):
    """Run gnsstool's CLI in-process; return (exit code, stdout)."""
    out = io.StringIO()
    with mock.patch.object(sys, 'argv', ['gnsstool', *argv]), contextlib.redirect_stdout(out):
        try:
            gnsstool.main()
        except SystemExit as e:
            return e.code, out.getvalue()
    return None, out.getvalue()


class HelpTest(unittest.TestCase):
    def test_help_command_matches_command_dash_dash_help(self):
        for command in ('elevation', 'platform', 'completion', 'version'):
            with self.subTest(command=command):
                self.assertEqual(run_cli('help', command), run_cli(command, '--help'))

    def test_help_alone_shows_top_level_help(self):
        self.assertEqual(run_cli('help'), run_cli('--help'))

    def test_help_rejects_unknown_command(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = run_cli('help', 'nope')
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
