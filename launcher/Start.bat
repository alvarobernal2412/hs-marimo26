@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem The runtime (Python and the notebooks) is one archive next to this file. It is unpacked once, outside any synced folder, with
rem Windows' own tar (System32's: it reads zip; a Git-for-Windows tar earlier on the PATH does not). !VARIABLES! keep a ")" in a path
rem from closing the blocks below.
rem Safe to interrupt and repeat (window closed, laptop shut down): the archive is unpacked into "runtime.new", marked complete
rem INSIDE it, and only then swapped in as "runtime". A half-unpacked "runtime.new" is thrown away on the next start; a complete
rem one is only swapped in.
set "RT=%LOCALAPPDATA%\hs-marimo26\runtime"
set "NEW=!RT!.new"
set "ZIP=%~dp0runtime.zip"
set "TAR=%SystemRoot%\System32\tar.exe"
set /p PKG=<package-id.txt
set "READY="
if exist "!RT!\ready-!PKG!" if exist "!RT!\python\python.exe" set "READY=1"
if not defined READY (
  if not exist "!NEW!\ready-!PKG!" (
    echo Setting up the course tools. This takes a few minutes the first time, please wait and keep this window open...
    if exist "!NEW!" rmdir /s /q "!NEW!"
    mkdir "!NEW!"
    "!TAR!" -xf "!ZIP!" -C "!NEW!"
    if errorlevel 1 (
      echo This computer has no quick unzip tool, so this can take a long while. Please keep this window open...
      powershell -NoProfile -Command "Expand-Archive -LiteralPath '!ZIP!' -DestinationPath '!NEW!' -Force"
    )
    if errorlevel 1 (
      echo Setting up did not work. Please send a photo of this window to your teachers.
      pause
      exit /b 1
    )
    type nul > "!NEW!\ready-!PKG!"
  ) else (
    echo Finishing the setup of the course tools...
  )
  if exist "!RT!" rmdir /s /q "!RT!"
  rem a virus scanner can still hold the new files for a moment: try the swap a few times
  set "MOVED="
  for /l %%i in (1,1,10) do if not defined MOVED (
    move "!NEW!" "!RT!" >nul 2>nul && set "MOVED=1"
    if not defined MOVED timeout /t 3 /nobreak >nul 2>nul
  )
  if not defined MOVED (
    echo Setting up did not work. Please send a photo of this window to your teachers.
    pause
    exit /b 1
  )
)
"!RT!\python\python.exe" -s "%~dp0launcher\start.py" "!RT!" %*
pause
