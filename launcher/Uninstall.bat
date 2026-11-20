@echo off
setlocal enabledelayedexpansion
rem Removes everything the course tools keep on THIS computer, after showing what that means and asking. The folder this file is in
rem stays (delete it yourself). Plain batch, no Python: the runtime's own Python is part of what is removed, and Windows cannot delete
rem the folder of a program that is running.
set "TOOLS=%LOCALAPPDATA%\hs-marimo26"
set "WORK=%USERPROFILE%\.hs-marimo26"
set "COPIES=%TEMP%\bpm-provenance"

set "ANY="
if exist "!TOOLS!" set "ANY=1"
if exist "!WORK!" set "ANY=1"
if exist "!COPIES!" set "ANY=1"
if not defined ANY (
  echo Nothing to remove: the course tools are not set up on this computer.
  pause
  exit /b 0
)

rem the notebooks keep files open while they run: they have to be closed first
if exist "!WORK!\running.port" (
  set "PORT="
  set /p PORT=<"!WORK!\running.port"
  if defined PORT (
    powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient('127.0.0.1', [int]$env:PORT); $c.Close(); exit 0 } catch { exit 1 }"
    if not errorlevel 1 (
      echo The notebooks are running. Close their window first, then double-click Uninstall again.
      pause
      exit /b 1
    )
  )
)

echo Measuring what is on this computer, one moment...
set "SIZES="
for /f "usebackq delims=" %%s in (`powershell -NoProfile -Command "function mb($p) { if (Test-Path -LiteralPath $p) { [int][math]::Round((Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB) } else { -1 } }; '{0} {1} {2}' -f (mb (Join-Path $env:LOCALAPPDATA 'hs-marimo26')), (mb (Join-Path $env:USERPROFILE '.hs-marimo26')), (mb (Join-Path $env:TEMP 'bpm-provenance'))"`) do set "SIZES=%%s"
set "MB_TOOLS=-1"
set "MB_WORK=-1"
set "MB_COPIES=-1"
for /f "tokens=1-3" %%a in ("!SIZES!") do (
  set "MB_TOOLS=%%a"
  set "MB_WORK=%%b"
  set "MB_COPIES=%%c"
)
set "SHOW_TOOLS=about !MB_TOOLS! MB"
set "SHOW_WORK=about !MB_WORK! MB"
set "SHOW_COPIES=about !MB_COPIES! MB"
if "!MB_TOOLS!"=="-1" set "SHOW_TOOLS=not there"
if "!MB_WORK!"=="-1" set "SHOW_WORK=not there"
if "!MB_COPIES!"=="-1" set "SHOW_COPIES=not there"
if "!MB_TOOLS!"=="0" set "SHOW_TOOLS=less than 1 MB"
if "!MB_WORK!"=="0" set "SHOW_WORK=less than 1 MB"
if "!MB_COPIES!"=="0" set "SHOW_COPIES=less than 1 MB"

echo.
echo ================================================================
echo   Remove the course tools from this computer
echo ================================================================
echo.
echo This will delete, on THIS computer:
echo.
echo   1. The course tools (Python and the notebooks): !SHOW_TOOLS!
echo        %LOCALAPPDATA%\hs-marimo26
echo   2. Your analyses saved here (the provenance): !SHOW_WORK!
echo        %USERPROFILE%\.hs-marimo26
echo   3. Temporary copies of your analyses: !SHOW_COPIES!
echo        %TEMP%\bpm-provenance
echo.
echo WHAT THIS MEANS FOR YOUR WORK
echo   - If you said YES to sharing: a copy of your analyses is on the course server, under your key. This does NOT remove it.
echo     After you set the tools up again, enter the same key and your work comes back. To have the server copy deleted too,
echo     ask your teachers.
echo   - If you said NO to sharing, or never entered a key: your analyses exist ONLY on this computer. After this they are gone
echo     for good and cannot be brought back.
echo   - Your answer about sharing is forgotten: you are asked again the next time you start.
echo   - Your web browser still remembers your key and your chart settings for this page. On a shared computer, clear the
echo     site data for localhost in the browser.
echo   - The folder with Start in it is not removed. To use the course tools again, double-click Start: the setup takes a few
echo     minutes.
echo.
echo Type YES and press Enter to remove everything.
echo Anything else (just pressing Enter, or closing this window) cancels, and nothing is removed.
set "ANSWER="
set /p "ANSWER=> "
if /i not "!ANSWER!"=="YES" (
  echo.
  echo Cancelled. Nothing was removed.
  pause
  exit /b 0
)

echo.
echo Removing...
if exist "!TOOLS!" rmdir /s /q "!TOOLS!"
if exist "!WORK!" rmdir /s /q "!WORK!"
if exist "!COPIES!" rmdir /s /q "!COPIES!"

set "LEFT="
if exist "!TOOLS!" set "LEFT=1"
if exist "!WORK!" set "LEFT=1"
if exist "!COPIES!" set "LEFT=1"
if defined LEFT (
  echo.
  echo Not everything could be removed: something is still using it. Close every course window, wait a moment, and run this again.
  pause
  exit /b 1
)
echo.
echo Everything was removed.
pause
