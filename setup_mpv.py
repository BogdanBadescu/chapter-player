"""Descarca libmpv-2.dll (ultimul build shinchiro) langa player.py.
Foloseste 7zr.exe (7-Zip oficial) pentru dezarhivare - fara pachete Python extra."""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest"
SEVENZR = "https://www.7-zip.org/a/7zr.exe"
HEADERS = {"User-Agent": "chapter-player-setup"}


def get(url, api=False):
    headers = dict(HEADERS)
    # in GitHub Actions: token doar pentru api.github.com (evita limita de cereri)
    if api and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main():
    dst = os.path.join(BASE, "libmpv-2.dll")
    if os.path.exists(dst):
        print("libmpv-2.dll exista deja.")
        return 0

    print("Caut ultima versiune libmpv...")
    rel = json.loads(get(API, api=True))
    asset = next(
        (a for a in rel["assets"] if re.match(r"^mpv-dev-x86_64-\d", a["name"])),
        None,
    )
    if not asset:
        print("Nu am gasit arhiva mpv-dev pe GitHub.")
        return 1

    tmp = tempfile.mkdtemp()
    try:
        print("Descarc extractorul 7zr.exe ...")
        exe = os.path.join(tmp, "7zr.exe")
        with open(exe, "wb") as f:
            f.write(get(SEVENZR))

        print(f"Descarc {asset['name']} ...")
        arc = os.path.join(tmp, "mpv.7z")
        with open(arc, "wb") as f:
            f.write(get(asset["browser_download_url"]))

        out = os.path.join(tmp, "out")
        subprocess.run([exe, "x", arc, f"-o{out}", "-y"], check=True,
                       stdout=subprocess.DEVNULL)

        found = [p for p in glob.glob(os.path.join(out, "**", "*.dll"), recursive=True)
                 if os.path.basename(p).lower() in ("libmpv-2.dll", "mpv-2.dll")]
        if not found:
            print("DLL-ul nu e in arhiva.")
            return 1
        shutil.copyfile(found[0], dst)
        print("Gata: libmpv-2.dll instalat.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
