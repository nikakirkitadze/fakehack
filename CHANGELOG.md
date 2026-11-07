# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-11-07

### Added
- `fakehack tv`: cast the hacked screen straight to an **LG webOS TV** over Wi-Fi,
  with no screen mirroring — the TV opens the hosted page in its own browser.
  A one-time on-screen pairing (accept once with the remote), then every cast is
  silent and instant; the client-key is stored in `~/.config/fakehack/lgtv.json`.
- Built-in, **dependency-free** webOS SSAP client: modern `ssl` over a hand-rolled
  secure WebSocket, with a registration manifest that avoids the "test" signature
  blacklisted by 2023+ firmware.
- SSDP auto-discovery of the TV when `--ip` is omitted.
- `docs/index.html`: a standalone hosted version of the screen (GitHub Pages) with
  URL-param config (`?word`, `?target`, `?msg`, `?headline`, `?duration`, `?auto`),
  loadable by any smart-TV browser.

[1.1.0]: https://github.com/nikakirkitadze/fakehack/releases/tag/v1.1.0

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
