# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-11-07

### Added
- Initial release.
- Full-screen terminal takeover: glitching block-letter banner, fake Hollywood
  hacker log, climbing ACCESS bar, blinking "DO NOT POWER OFF" warning.
- Timed run (`--duration`) with early exit on any keypress, then a big **GOTCHA**
  reveal.
- Always restores the terminal (alternate screen, cursor, colors) on exit,
  Ctrl-C, or error.
- Flags: `--duration`, `--word`, `--target`, `--message`, `--fps`, `--no-reveal`,
  `--selftest`, `--version`.
- Zero dependencies — Python 3.8+ standard library only.

[1.0.0]: https://github.com/nikakirkitadze/fakehack/releases/tag/v1.0.0
