# hs-marimo26

The course notebooks as a package students run on their own laptop: no Docker, no install, no terminal.

- `notebooks/`: `00_lecture-initial-analysis.py`, `01_assignment-initial-analysis.py`, `02_lecture-process-map.py` (maps of the
  Sepsis log) and `03_assignment-process-map.py`, and what they share (`bpm_kit.py`, `lib/`, `data/`). The two lecture notebooks
  record and save nothing and ask for no key. `marimo run` serves them as a gallery of apps, under the title each one sets
  (`app_title`). The two assignment notebooks read a log that is not public (see "The log that is not public").
- `launcher/`: `Start.bat` / `Start.command` (at the package root: unpack the runtime on the first start, then run `start.py`),
  `Change-my-answer.bat` / `.command` (the same with `--consent`), `Remove-my-data.bat` / `.command` (the same with `--remove-data`), `removal.py` (the page that removes one assignment's saved work from the course server, keeping a copy for the teachers; refuses while the notebooks run), `start.py` (update, ask for consent, fetch the log that is not public, start marimo, open the browser),
  `update.py`, `coursefiles.py` (the one-time course code page and the download), `consent.py` (the one-time consent page; the answer is kept in `~/.hs-marimo26/consent.json`; unless it is "accepted"
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
- `Uninstall.bat` / `Uninstall.command` remove the tools, `~/.hs-marimo26` (consent answer, course code and work kept without a key) and the temporary
  session copies, after showing the impact and asking for `YES` (pure batch/bash: the runtime's Python is part of what is removed).
  They never touch the course server's copy of a student's work, the browser's stored key, or the folder the zip was unpacked to.
- The notebooks are numbered (`00_` to `03_`) so the gallery lists them in course order. The notebook ids the course server knows
  them by (`initial-analysis`, `map-explorer` in `lib/initial_analysis_kit.py`) are unchanged: they name students' saved work.
- `notebooks/vendor/provenance_widget` is a copy of marimo-pmprov that the notebooks import before the installed one (they put
  `vendor/` first on the path). A start only brings `notebooks/` up to date, so this is how a new version of marimo-pmprov
  reaches students without a new package: `python build/vendor_library.py --wheel <the released wheel>` (or `--checkout`),
  commit, release a MINOR. `vendor/VENDORED.json` names the version and a hash of the files (`tests/test_vendored_library.py`:
  never edit the copy by hand). It works for a version that needs no library the package lacks; when `build/requirements.txt`
  has to change, that is a MAJOR. The installed marimo-pmprov stays as it is and is only used where there is no `vendor/`.
- Every table of a notebook is drawn by a cell of its own (`00`, `01` and `03`): a group of tabs is only the strip (`mo.ui.tabs`
  with empty panels) and each table is shown by the next cells when its tab is selected. marimo keeps the charts built with
  *Visualize* in the browser, under the id of the cell that draws the table, so tables that share a cell share their charts
  (`tests/test_one_table_per_cell.py`). marimo-pmprov (0.16) keeps the recorded charts by the name of their table, which it
  finds by the `artifact_name` written in the cell that shows it, so they come back on their own tables also after a notebook
  gained or lost cells (the page is loaded again once, the first time a browser opens such a notebook). `00` records nothing:
  there a browser that saved charts under other cells starts without them.
- Dragging a node of the map in `03_assignment-process-map.py` is a recorded step (`arrange_map`, with
  `provenance_widget.arrangement`): the page reports where the nodes were dragged to, the notebook records it and draws the map
  with the nodes there, so an annotation written after it shows the map as arranged (and is its own figure in the report), and
  a notebook that is opened again shows the map as it was left. A map that is drawn again (Refresh) starts as it is drawn.
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
- Every notebook shows the version of the notebooks (`ak.notebooks_version`, read from the `version.json` beside `notebooks/`, or "development copy") and a "Stop the app" button at the top right (`ak.app_bar`, `ak.stop_confirmation`, `ak.stop_app`). They live in the notebooks, so they ship as a MINOR; the line in the terminal about an update waits for the next MAJOR.
- The process maps (`02` and `03`) let the student choose the activity column and a time frame, and the event log has a `lifecycle_state` column ("on" or "off", `ak.add_lifecycle_state`) and the case log a `duration` column (`ak.to_lcm_log`, `ak.cases_in_time_frame`, `ak.build_case_log`).

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

The manifest also names the build (the commit), and a release publishes it as a file of its own (`manifest.json`). A launcher whose
version equals the latest release asks for that small file: if the build differs, the version was published again with other
contents, and it is applied like a MINOR (new notebooks, or the "new version" page when the libraries changed). A changed launcher
still only arrives with the install line, so that needs a new MAJOR.

To release: `git tag v1.1.0 && git push origin v1.1.0` (or run the *release* workflow by hand with a version). CI builds everything and
leaves a **draft**. Download the zips from the draft and try them, then press **Publish release**: only then do students and launchers
see it. A launcher applies the latest release when it has the same MAJOR as the copy it started from.

## The log that is not public

The log of the two assignment notebooks may not be published, so it is in no commit, package or release of this repository. The
repository only names it: `notebooks/data/dhana-loan-application.parquet.sha256` holds the hash of the file the notebooks expect.
A file with such a hash file next to it is never shipped (`is_private` in `build/make_notebooks_zip.py`), so a developer can keep a
copy in `notebooks/data/` (git ignores it).

Students get it from the course server (provenance-sync, "Course files" in its README): the
launcher (`coursefiles.py`) asks once for the course code, downloads `/v1/files/<name>` with it, checks the hash and puts the file
into the runtime's `notebooks/data/`. The code is kept in `~/.hs-marimo26/course-code.txt`. A student who skips the page still
starts; the assignment notebooks then say that the log is missing, and the next start asks again. `HS_FILES_URL` names another
server; an empty value turns fetching off.

To change the log: put the new file on the server (`data/files/` there), write its hash into the `.sha256` file
(`sha256sum notebooks/data/dhana-loan-application.parquet`) and release. Launchers fetch the new file with the saved code, without
asking. To change the course code, change `PS_FILES_CODE` on the server: computers that already have the log keep working.

Students' own files stay outside the package, in `~/.hs-marimo26/`: `provenance/` (work saved without a key) and `synced/` (the
local copy of work saved with a key, one folder per key and notebook; the course server holds the other copy). A notebook opened
without a connection works from the local copy and sends it when the server is back. If there is no local copy either, it starts
empty and never replaces what the server holds: it asks for a reload, which loads the saved work and keeps the rest in a folder
beside it (`*.unsynced-<time>`). The updater never removes anything from `notebooks/data/` or `notebooks/provenance/`.

## Develop
`pip install -r build/requirements.txt pytest`, then `pytest tests` and `marimo run notebooks`.
