# Chapter Player

Player audio pentru Windows, cu toată înregistrarea pe o singură bară de progres, forma de undă, marcaje de capitol și listă de capitole. Gândit pentru înregistrări făcute în Audacity (mp3/m4a + fișier de etichete exportat cu *Export Labels*).

## Funcții
- toată înregistrarea pe o singură bară, cu marcaje de capitol
- forma de undă (click pentru salt)
- listă de capitole cu durata fiecăruia
- citește etichetele Audacity (`început<TAB>sfârșit<TAB>titlu`)
- viteză 0.5x–3.0x din 0.1 în 0.1
- scurtături: Space, ←/→ ±10 s, ↑/↓ capitol următor/anterior, `<` `>` viteză
- reia poziția la redeschiderea fișierului (opțional)
- funcționează offline

## Utilizare
1. Pornește `ChapterPlayer.exe`.
2. **Selectare înregistrare** și, dacă e nevoie, **Selectare markere** (fișierul `.txt` din Audacity).
   Dacă fișierul `.txt` are același nume cu înregistrarea și e în același folder, e găsit automat.

## Construire din sursă
```
pip install -r requirements.txt pyinstaller
python setup_mpv.py
pyinstaller --onefile --windowed --name ChapterPlayer --icon app_icon.ico ^
  --add-binary "libmpv-2.dll;." --add-data "app_icon.ico;." player.py
```
Build-ul oficial se face în GitHub Actions (`.github/workflows/build.yml`).

## Licență
GPL-3.0-or-later, vezi `LICENSE`. Folosește:
- [PySide6 / Qt](https://www.qt.io/qt-for-python) (LGPL-3.0)
- [libmpv](https://mpv.io/) (build-uri shinchiro, GPL-2.0-or-later)
- [python-mpv](https://github.com/jaseg/python-mpv) (GPL-2.0-or-later / LGPL-2.1-or-later)
- [NumPy](https://numpy.org/) (BSD-3-Clause)

## Politica de semnare a codului
Executabilele publicate sunt construite automat în GitHub Actions din acest repository și semnate cu SignPath (după aprobare).
