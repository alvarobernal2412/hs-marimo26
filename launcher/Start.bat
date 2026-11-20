@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem The runtime (Python and the notebooks) is one archive next to this file. It is unpacked once, outside any synced folder, with
rem Windows' own tar (System32's: it reads zip; a Git-for-Windows tar earlier on the PATH does not). !VARIABLES! keep a ")" in a path
rem from closing the block below.
set "RT=%LOCALAPPDATA%\hs-marimo26\runtime"
set "ZIP=%~dp0runtime.zip"
set "TAR=%SystemRoot%\System32\tar.exe"
set /p PKG=<package-id.txt
if not exist "!RT!\ready-!PKG!" (
  echo Setting up the course tools. This takes a minute or two the first time, please wait...
  if exist "!RT!" rmdir /s /q "!RT!"
  mkdir "!RT!"
  "!TAR!" -xf "!ZIP!" -C "!RT!"
  if errorlevel 1 (
    echo This computer has no quick unzip tool, so this can take a long while. Please keep this window open...
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '!ZIP!' -DestinationPath '!RT!' -Force"
  )
  if errorlevel 1 (
    echo Setting up did not work. Please send a photo of this window to your teachers.
    pause
    exit /b 1
  )
  type nul > "!RT!\ready-!PKG!"
)
"!RT!\python\python.exe" -s "%~dp0launcher\start.py" "!RT!" %*
pause
