"""
Behavioural tests for gnsstool's generated shell completion scripts.

Each test sources the generated script in a real shell, simulates the words
typed so far, and checks what Tab would offer. This catches both broken shell
syntax and a CLI change the completion doesn't reflect.

bash: drives the completion function with COMP_WORDS/COMP_CWORD, as readline does.
zsh:  stubs zsh's _describe builtin to print the candidates it would display, so
      no interactive terminal is needed.

Tests for a shell are skipped if that shell isn't installed.
Run: python3 -m unittest discover -s roles/gnsstool/tests
"""

import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.modules.setdefault('smbus2', types.ModuleType('smbus2'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'files'))

import gnsstool  # noqa: E402

PARSER = gnsstool.build_parser()

TOP_LEVEL = ['completion', 'elevation', 'help', 'platform', 'satellites', 'status', 'version']


def _write_script(text):
    f = tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False)
    f.write(text + '\n')
    f.close()
    return f.name


@unittest.skipUnless(shutil.which('bash'), 'bash not installed')
class BashCompletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _write_script(gnsstool.completion_bash(PARSER))

    def complete(self, line):
        """Return the sorted candidates bash would offer for `line` (cursor at end)."""
        harness = (
            f'source {self.script}\n'
            f'COMP_WORDS=({line}); COMP_CWORD=$(( ${{#COMP_WORDS[@]}} - 1 ))\n'
            '_gnsstool\n'
            'printf "%s\\n" "${COMPREPLY[@]}"\n'
        )
        out = subprocess.run(['bash', '-c', harness], capture_output=True, text=True, check=True)
        return sorted(w for w in out.stdout.split('\n') if w)

    def test_registers_completion_function(self):
        out = subprocess.run(['bash', '-c', f'source {self.script}; complete -p gnsstool'],
                             capture_output=True, text=True, check=True)
        self.assertIn('-F _gnsstool gnsstool', out.stdout)

    def test_top_level_commands(self):
        self.assertEqual(self.complete("gnsstool ''"),
                         TOP_LEVEL)

    def test_partial_word_is_completed(self):
        self.assertEqual(self.complete('gnsstool el'), ['elevation'])

    def test_platform_set_offers_modes(self):
        self.assertEqual(self.complete("gnsstool platform set ''"), ['portable', 'stationary'])

    def test_elevation_set_offers_suggestions(self):
        self.assertEqual(self.complete("gnsstool elevation set 1"), ['10', '15'])

    def test_help_offers_commands(self):
        self.assertEqual(self.complete("gnsstool help ''"), TOP_LEVEL)

    def test_top_level_options_include_version(self):
        self.assertEqual(self.complete('gnsstool --'), ['--help', '--version'])

    def test_completion_offers_shells(self):
        self.assertEqual(self.complete("gnsstool completion ''"), ['bash', 'zsh'])

    def test_options_ignored_when_tracking_position(self):
        self.assertEqual(self.complete("gnsstool --help platform ''"), ['set', 'status'])

    def test_nothing_after_final_argument(self):
        self.assertEqual(self.complete("gnsstool platform set stationary ''"), [])


@unittest.skipUnless(shutil.which('zsh'), 'zsh not installed')
class ZshCompletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _write_script(gnsstool.completion_zsh(PARSER))

    def complete(self, *typed):
        """Return the `word[:description]` entries zsh would display after `typed` words."""
        words = ' '.join(f"'{w}'" for w in ('gnsstool',) + typed)
        harness = (
            # Stand-in for zsh's _describe: print the named candidates array
            '_describe() { print -rl -- "${(@P)${@[-1]}}" }\n'
            f'words=({words}); CURRENT=${{#words}}\n'
            f'source {self.script}\n'
        )
        out = subprocess.run(['zsh', '-f', '-c', harness], capture_output=True, text=True)
        return [line for line in out.stdout.split('\n') if line]

    def test_syntax(self):
        subprocess.run(['zsh', '-n', self.script], check=True)

    def test_top_level_commands_with_descriptions(self):
        entries = dict(e.split(':', 1) for e in self.complete(''))
        self.assertEqual(sorted(entries), TOP_LEVEL)
        self.assertIn('elevation mask', entries['elevation'])

    def test_platform_set_offers_modes(self):
        self.assertEqual(sorted(self.complete('platform', 'set', '')), ['portable', 'stationary'])

    def test_elevation_set_offers_suggestions(self):
        self.assertEqual(self.complete('elevation', 'set', ''), ['10', '15', '20'])

    def test_nothing_after_final_argument(self):
        self.assertEqual(self.complete('platform', 'set', 'stationary', ''), [])


if __name__ == '__main__':
    unittest.main()
