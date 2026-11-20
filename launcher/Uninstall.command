#!/bin/bash
# Removes everything the course tools keep on THIS computer, after showing what that means and asking. The folder this file is in
# stays (delete it yourself). Plain bash, no Python: the runtime's own Python is part of what is removed.
TOOLS="$HOME/Library/Application Support/hs-marimo26"
WORK="$HOME/.hs-marimo26"
COPIES="${TMPDIR:-/tmp}"
COPIES="${COPIES%/}/bpm-provenance"

if [ ! -e "$TOOLS" ] && [ ! -e "$WORK" ] && [ ! -e "$COPIES" ]; then
  echo "Nothing to remove: the course tools are not set up on this computer."
  read -r -p "Press Return to close this window. " _
  exit 0
fi

# the notebooks keep files open while they run: they have to be closed first
if [ -f "$WORK/running.port" ]; then
  PORT="$(head -n 1 "$WORK/running.port" | tr -dc '0-9')"
  if [ -n "$PORT" ] && (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
    echo "The notebooks are running. Close their window first, then double-click Uninstall again."
    read -r -p "Press Return to close this window. " _
    exit 1
  fi
fi

size() {  # "about N MB", "less than 1 MB" or "not there"
  if [ ! -e "$1" ]; then echo "not there"; return; fi
  local mb=$(( $(du -sk "$1" 2>/dev/null | cut -f1) / 1024 ))
  if [ "$mb" -lt 1 ]; then echo "less than 1 MB"; else echo "about $mb MB"; fi
}

echo "Measuring what is on this computer, one moment..."
echo
echo "================================================================"
echo "  Remove the course tools from this computer"
echo "================================================================"
echo
echo "This will delete, on THIS computer:"
echo
echo "  1. The course tools (Python and the notebooks): $(size "$TOOLS")"
echo "       $TOOLS"
echo "  2. Your analyses saved here (the provenance): $(size "$WORK")"
echo "       $WORK"
echo "  3. Temporary copies of your analyses: $(size "$COPIES")"
echo "       $COPIES"
echo
echo "WHAT THIS MEANS FOR YOUR WORK"
echo "  - If you said YES to sharing: a copy of your analyses is on the course server, under your key. This does NOT remove it."
echo "    After you set the tools up again, enter the same key and your work comes back. To have the server copy deleted too,"
echo "    ask your teachers."
echo "  - If you said NO to sharing, or never entered a key: your analyses exist ONLY on this computer. After this they are gone"
echo "    for good and cannot be brought back."
echo "  - Your answer about sharing is forgotten: you are asked again the next time you start."
echo "  - Your web browser still remembers your key and your chart settings for this page. On a shared computer, clear the"
echo "    site data for localhost in the browser."
echo "  - The folder with Start in it is not removed. To use the course tools again, double-click Start: the setup takes a few"
echo "    minutes."
echo
echo "Type YES and press Enter to remove everything."
echo "Anything else (just pressing Enter, or closing this window) cancels, and nothing is removed."
printf '> '
read -r ANSWER
if [ "$(printf '%s' "$ANSWER" | tr '[:lower:]' '[:upper:]')" != "YES" ]; then
  echo
  echo "Cancelled. Nothing was removed."
  read -r -p "Press Return to close this window. " _
  exit 0
fi

echo
echo "Removing..."
rm -rf "$TOOLS" "$WORK" "$COPIES"

if [ -e "$TOOLS" ] || [ -e "$WORK" ] || [ -e "$COPIES" ]; then
  echo
  echo "Not everything could be removed: something is still using it. Close every course window, wait a moment, and run this again."
  read -r -p "Press Return to close this window. " _
  exit 1
fi
echo
echo "Everything was removed."
read -r -p "Press Return to close this window. " _
exit 0
