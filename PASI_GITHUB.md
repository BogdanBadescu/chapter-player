# Pașii pentru GitHub și SignPath (doar tu poți face asta, necesită contul tău)

1. **Cont GitHub:** https://github.com/signup (dacă nu ai deja).
2. **Repo nou, PUBLIC:** New repository → nume `chapter-player` → Public → fără README (avem deja unul).
3. **Încarcă fișierele:** pe pagina repo-ului, „uploading an existing file". Trage TOT conținutul acestui folder:
   `player.py`, `setup_mpv.py`, `app_icon.ico`, `LICENSE`, `README.md`, `requirements.txt`, `.gitignore`, `CERERE_SIGNPATH.md`
   și folderul `.github` (cu `workflows/build.yml` în el). Dacă browserul nu acceptă folderul ascuns, folosește
   „Add file → Create new file", numele `.github/workflows/build.yml`, și lipește conținutul.
   Apoi Commit.
4. **Primul build:** tab-ul **Actions** → „Build Windows exe" → **Run workflow**. Durează ~5–10 minute.
   La final, în pagina rulării, la **Artifacts** descarci `ChapterPlayer-unsigned` (exe nesemnat; Smart App Control îl blochează încă).
   Dacă build-ul pică, copiază-mi eroarea din log.
5. **Aplică la SignPath Foundation** cu textul din `CERERE_SIGNPATH.md` (înlocuiește `<UTILIZATOR>`, numele și email-ul).
6. **După aprobare:** în repo, Settings → Secrets and variables → Actions:
   secret `SIGNPATH_API_TOKEN`, variabilă `SIGNPATH_ORGANIZATION_ID` (le primești de la SignPath).
   În `build.yml`, schimbă `if: false` în `if: true` la jobul `sign`. Rulează din nou workflow-ul.
   Artifact-ul `ChapterPlayer-signed` conține exe-ul semnat.
