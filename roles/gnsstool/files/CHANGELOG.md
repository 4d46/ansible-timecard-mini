# Changelog

All notable changes to `gnsstool` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the version follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **major** — a command or option is removed or changes meaning
- **minor** — a new command, option or output column
- **patch** — a fix that doesn't change how the tool is used

Bump `__version__` in `gnsstool.py` and add an entry here in the same PR.
`gnsstool version` also reports the repository commit the tool was deployed from.

## [1.1.0] - 2026-10-03

### Added
- `elevation` and `elevation set <degrees>` to show and set the minimum satellite
  elevation mask (CFG-NAVSPG-INFIL_MINELEV), RAM only.
- `completion bash|zsh` to print shell completion scripts generated from the CLI
  definition; Ansible installs them for the shells in `gnsstool_shell_completions`.
- `help [command]` and `version` subcommands, plus a `--version` option.

### Changed
- `satellites` constellation summary: the `SVs` column is replaced by `Tracked`
  (signal received) and `Used` (in the fix). `SVs` counted satellites the chip knew
  about but wasn't receiving, so it didn't match the satellite list below it.

### Fixed
- Signed configuration values are encoded and decoded correctly.

## [1.0.0] - 2026-05-16

### Added
- `status`, `satellites`, `platform` and `platform set stationary|portable`.
