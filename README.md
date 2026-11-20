# hs-marimo26

The course notebooks as a package students run on their own laptop: no Docker, no install, no terminal.

- `notebooks/`: `lecture.py`, `initial-analysis.py`, `map-explorer.py` and what they share (`bpm_kit.py`, `lib/`, `data/`). `marimo run`
  serves them as a gallery of apps. The Dhana log is read from `data/dhana-loan-application-molab.xes`.
- `launcher/`: `Start.bat` / `Start.command` (at the package root: unpack the runtime on the first start, then run `start.py`),
  `Change-my-answer.bat` / `.command` (the same with `--consent`), `start.py` (update, ask for consent, start marimo, open the browser),
  `update.py`, `consent.py` (the one-time consent page; the answer is kept in `~/.hs-marimo26/consent.json`; unless it is "accepted"
  the notebooks run with `PMPROV_SYNC_URL=""`, i.e. without the course server; `--consent` asks again, and refuses while the notebooks run).
- The student zip is two layers, so unzipping it is quick (Explorer's unzip is slow on tens of thousands of files): a few loose files
  (`Start.*`, `Change-my-answer.*`, `launcher/`, `README-students.md`, `package-id.txt`) plus ONE runtime archive (`runtime.zip` on
  Windows, `runtime.tar.gz` on Mac: `python/`, `notebooks/`, `version.json`). The first start unpacks it with the system's own `tar` into
  `%LOCALAPPDATA%\hs-marimo26\runtime` (Windows) or `~/Library/Application Support/hs-marimo26/runtime` (Mac), marked by `ready-<version>`;
  `start.py` and `update.py` work on that folder.
- `build/`: `build_runtime.py` makes the per-OS student zip, `make_notebooks_zip.py` the `notebooks.zip` of a release.
- `.github/workflows/release.yml`: on a `v*` tag, builds the three student zips and `notebooks.zip` and drafts the release.

## Releases

One version, `vMAJOR.MINOR.PATCH`, and one link for students: `https://github.com/alvarobernal2412/hs-marimo26/releases/latest`.
A release holds the three student zips (`hs-marimo26-v<version>-windows-x64.zip`, `-macos-arm64.zip`, `-macos-x64.zip`) and
`notebooks.zip`, which running copies fetch by themselves when they start.

| Bump | When | What students do |
|---|---|---|
| MAJOR | the package changes: Python, libraries, the data folder | download the new zip (their launcher tells them) |
| MINOR or PATCH | only `notebooks/` changes | nothing: it updates on the next start |

To release: `git tag v1.1.0 && git push origin v1.1.0` (or run the *release* workflow by hand with a version). CI builds everything and
leaves a **draft**. Download the zips from the draft and try them, then press **Publish release**: only then do students and launchers
see it. A launcher applies the latest release when it has the same MAJOR as the copy it started from.

The two Dhana `.xes` logs are too big for git. They live as files of the release tagged `datasets` (replace the files there when
the logs change); the build puts them into every student zip, together with a `.csv` made from the parquet the notebooks read.

Students' own files stay outside the package: `~/.hs-marimo26/` (work saved without a key) and the key's session folder in the temp
directory (the course server holds the real copy). The updater never touches `notebooks/data/` or `notebooks/provenance/`.

## Develop
`pip install -r build/requirements.txt pytest`, then `pytest tests` and `marimo run notebooks`.
