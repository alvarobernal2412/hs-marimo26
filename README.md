# hs-marimo26

The course notebooks as a package students run on their own laptop: no Docker, no install, no terminal.

- `notebooks/`: `00_lecture.py`, `01_map-explorer.py` (maps of the Sepsis log; nothing recorded or saved, no key),
  `02_initial-analysis.py`, `03_map-explorer.py` and what they share (`bpm_kit.py`, `lib/`, `data/`). `marimo run`
  serves them as a gallery of apps. The Dhana log is read from `data/dhana-loan-application-molab.xes`.
- `launcher/`: `Start.bat` / `Start.command` (at the package root: unpack the runtime on the first start, then run `start.py`),
  `Change-my-answer.bat` / `.command` (the same with `--consent`), `start.py` (update, ask for consent, start marimo, open the browser),
  `update.py`, `consent.py` (the one-time consent page; the answer is kept in `~/.hs-marimo26/consent.json`; unless it is "accepted"
  the notebooks run with `PMPROV_SYNC_URL=""`, i.e. without the course server; `--consent` asks again, and refuses while the notebooks run).
- The student zip (what the installer downloads) is two layers, so unpacking it is quick (Explorer's unzip is slow on tens of thousands of files): a few loose files
  (`Start.*`, `Change-my-answer.*`, `launcher/`, `START-HERE.txt` (the students' step-by-step, plain text so a double-click opens it),
  `package-id.txt`) plus ONE runtime archive (`runtime.zip` on Windows, `runtime.tar.gz` on Mac: `python/`, `notebooks/`, `version.json`).
  The first start unpacks it with the system's own `tar` into `runtime.new` beside `runtime` in `%LOCALAPPDATA%\hs-marimo26`
  (Windows) or `~/Library/Application Support/hs-marimo26` (Mac), writes `ready-<version>` inside it and only then swaps it in as
  `runtime`: closing the window or shutting the laptop down mid-setup is safe, the next start redoes the unpack (a complete `runtime.new`
  is only swapped in). `start.py` and `update.py` work on that folder.
- Windows runs python.org's embeddable Python (its `python.exe` is signed by the Python Software Foundation; the unsigned
  python-build-standalone one is blocked by managed laptops' Defender policy, "Access is denied"); Mac keeps python-build-standalone.
  The build smoke-tests the built Python (`SMOKE_MODULES`) before it zips anything.
- The Mac packages run on macOS 12 or later (`MAC_FLOOR`). pip on the build runner (macOS 15) picks the newest wheels that runner can
  use, which are built for macOS 14 or 15 (numpy, scipy, cvxopt) and do not load on an older Mac. The build installs those packages
  again in their build for macOS 12 or older and stops if any package is still too new (scipy's build for Apple chips is tagged
  macOS 12 but its files ask for 12.3). `install.sh` tells a student with an older macOS so, before it downloads anything.
- cvxopt is left out of every package (`LEFT_OUT`): it has no build for macOS 12, and pm4py uses it only when it is installed and
  solves with scipy otherwise. Leaving it out on Windows too gives every student the same solver.
- `package-id.txt` is the version plus `-<first 7 characters of the commit>` (CI passes `--build-id`): a computer that already unpacked
  that id does not unpack again, so the same version published again needs a new id to reach it. `version.json` inside the runtime keeps
  the plain version, which is what the updater compares.
- `Uninstall.bat` / `Uninstall.command` remove the tools, `~/.hs-marimo26` (consent answer and work kept without a key) and the temporary
  session copies, after showing the impact and asking for `YES` (pure batch/bash: the runtime's Python is part of what is removed).
  They never touch the course server's copy of a student's work, the browser's stored key, or the folder the zip was unpacked to.
- The notebooks are numbered (`00_` to `03_`) so the gallery lists them in course order. The notebook ids the course server knows
  them by (`initial-analysis`, `map-explorer` in `lib/initial_analysis_kit.py`) are unchanged: they name students' saved work.
- A student who said no to sharing has no course server in the analyst notebooks however they were started (`ak.course_server` reads
  `~/.hs-marimo26/consent.json`), not only through the launcher.
- `launcher/install.sh` / `install.ps1` are the terminal installers, published as files of every release (not inside the zips). A student pastes
  one line (printed in the release notes); the script finds the latest release through the public `releases/latest` redirect (no API call, so
  no rate limit for a classroom), downloads that OS's zip with curl / PowerShell, unpacks it to `~/hs-marimo26` (`%USERPROFILE%\hs-marimo26`)
  and runs Start. Files fetched by a command never get the browser's quarantine / mark-of-the-web, so there is no Gatekeeper dialog and no
  "Open Anyway": this is the ONLY way students get the tools (the zips on a release are what it downloads; a zip downloaded by a browser
  on a Mac would be quarantined again, and Start.command no longer clears that). Running it again updates the package and keeps other
  files in the folder. A computer that does not allow a terminal needs its IT department.
  The release build runs `install.sh` on both Mac runners (setup + the native files load).
- `build/`: `build_runtime.py` makes the per-OS student zip, `make_notebooks_zip.py` the `notebooks.zip` of a release.
- `.github/workflows/release.yml`: on a `v*` tag, builds the three student zips and `notebooks.zip` and drafts the release.

## Releases

One version, `vMAJOR.MINOR.PATCH`, and one link for students: `https://github.com/alvarobernal2412/hs-marimo26/releases/latest`.
A release holds the three student zips (`hs-marimo26-v<version>-windows-x64.zip`, `-macos-arm64.zip`, `-macos-x64.zip`) and
`notebooks.zip`, which running copies fetch by themselves when they start.

| Bump | When | What students do |
|---|---|---|
| MAJOR | the package changes: Python, libraries (`build/requirements.txt`), the launcher | paste the install line again (a page in their browser tells them, with the line to copy) |
| MINOR or PATCH | only `notebooks/` changes: notebooks added, changed or removed, small data files added | nothing: it updates on the next start |

Both the package and `notebooks.zip` carry a `manifest.json`: the notebook files the release ships and a hash of
`build/requirements.txt`. With it a launcher removes a notebook that a release dropped (never a file the student added), and does
not apply notebooks made for other libraries than it has: it shows the "new version" page instead. The release workflow refuses to
build a MINOR or PATCH whose libraries differ from the published release (`build/check_release.py`), so the number is right
before any student is affected. The launcher finds the latest release from the public release page, not the GitHub API, so a
classroom behind one address is never rate limited.

To release: `git tag v1.1.0 && git push origin v1.1.0` (or run the *release* workflow by hand with a version). CI builds everything and
leaves a **draft**. Download the zips from the draft and try them, then press **Publish release**: only then do students and launchers
see it. A launcher applies the latest release when it has the same MAJOR as the copy it started from.

The two Dhana `.xes` logs are too big for git. They live as files of the release tagged `datasets` (replace the files there when
the logs change); the build puts them into every student zip, together with a `.csv` made from the parquet the notebooks read.

Students' own files stay outside the package, in `~/.hs-marimo26/`: `provenance/` (work saved without a key) and `synced/` (the
local copy of work saved with a key, one folder per key and notebook; the course server holds the other copy). A notebook opened
without a connection works from the local copy and sends it when the server is back. If there is no local copy either, it starts
empty and never replaces what the server holds: it asks for a reload, which loads the saved work and keeps the rest in a folder
beside it (`*.unsynced-<time>`). The updater never removes anything from `notebooks/data/` or `notebooks/provenance/`.

## Develop
`pip install -r build/requirements.txt pytest`, then `pytest tests` and `marimo run notebooks`.
