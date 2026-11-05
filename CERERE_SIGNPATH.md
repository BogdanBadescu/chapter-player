# Text pentru cererea la SignPath Foundation (copiază în formular)

Aplică la: https://signpath.org/ (secțiunea Open Source / "Apply"). Verifică acolo cerințele actuale înainte să trimiți.

**Project name:** Chapter Player
**Repository URL:** https://github.com/<UTILIZATOR>/chapter-player
**Homepage:** același link ca repository-ul
**License:** GPL-3.0-or-later
**Short description:** Offline Windows audio player that shows a whole recording on a single progress bar with chapter markers, a waveform and a chapter list. It reads Audacity label files. Built with Python, PySide6 (Qt) and libmpv.

**Why code signing is needed:** The app is distributed as a single .exe for use on offline computers (copied on USB sticks / CDs). Windows 11 Smart App Control blocks unsigned executables, so users cannot run it without a valid signature.

**Build process:** The executable is built from source by a public GitHub Actions workflow (`.github/workflows/build.yml`) using PyInstaller. No manual builds are signed.

**Third-party components:** PySide6 (LGPL-3.0), libmpv (GPL-2.0-or-later), python-mpv, NumPy (BSD) — all open source.

**Maintainer:** <NUMELE TĂU>, <EMAIL>
