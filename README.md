# hs-marimo26

The course notebooks as a package students run on their own laptop: no Docker, no install, no terminal.

- `notebooks/`: `lecture.py`, `initial-analysis.py`, `map-explorer.py` and what they share (`bpm_kit.py`, `lib/`, `data/`). `marimo run`
  serves them as a gallery of apps. The Dhana log is read from `data/dhana-loan-application-molab.xes`.
- `launcher/`: `Start.bat` / `Start.command` (at the package root), `start.py` (update, start marimo, open the browser), `update.py`.
- `build/`: `build_runtime.py` makes the per-OS student zip, `make_notebooks_zip.py` the notebooks update.
- `.github/workflows/`: `runtime.yml` (manual) builds the three student zips; `notebooks.yml` publishes a notebooks update on a tag.

## Releases
| Release | What | When |
|---|---|---|
| `data-1` | the two Dhana `.xes` (too big for git), uploaded by hand | once, or when the logs change |
| `runtime-N` | `hs-marimo26-<os>-runtime<N>.zip` for windows-x64, macos-arm64, macos-x64: what students download | when packages change (`build/requirements.txt`) |
| `notebooks-N` | `notebooks.zip`: the update every launcher fetches on start | tag `notebooks-N` after changing `notebooks/` |

`build/min_runtime.txt` is the runtime number a notebooks release needs. Raise it only when `notebooks/` needs new packages: students on
an older runtime are told to download the package again and keep the notebooks they have.

Students' own files stay outside the package: `~/.hs-marimo26/` (work saved without a key) and the key's session folder in the temp
directory (the course server holds the real copy). The updater never touches `notebooks/data/` or `notebooks/provenance/`.

## Develop
`pip install -r build/requirements.txt pytest`, then `pytest tests` and `marimo run notebooks`.
