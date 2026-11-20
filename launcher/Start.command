#!/bin/bash
# The runtime (Python and the notebooks) is one archive next to this file. It is unpacked once with the Mac's own tar.
# Safe to interrupt and repeat (window closed, laptop shut down): the archive is unpacked into "runtime.new", marked complete INSIDE
# it, and only then swapped in as "runtime". A half-unpacked "runtime.new" is thrown away on the next start; a complete one is only
# swapped in.
cd "$(dirname "$0")"
HERE="$PWD"
RT="$HOME/Library/Application Support/hs-marimo26/runtime"
NEW="$RT.new"
PKG="$(cat package-id.txt)"
XATTR="${XATTR:-/usr/bin/xattr}"  # the tests replace it with a stand-in that logs its calls

# A download carries macOS's "quarantine" flag, and macOS then wants to approve every native file the tools load, one by one: hundreds
# of them, and it refuses them ("library load disallowed by system policy"). The student approved THIS file once; what is unpacked from
# the same download must not inherit the flag. xattr -dr clears it, needs no administrator rights, and only touches their own files.
strip_quarantine() { "$XATTR" -dr com.apple.quarantine "$@" 2>/dev/null || true; }

strip_quarantine "$HERE"  # the downloaded folder first: its archive would pass the flag on to what is unpacked from it

if [ ! -e "$RT/ready-$PKG" ] || [ ! -x "$RT/python/bin/python3" ]; then
  if [ ! -e "$NEW/ready-$PKG" ]; then
    echo "Setting up the course tools. This takes a few minutes the first time, please wait and keep this window open..."
    rm -rf "$NEW"
    mkdir -p "$NEW"
    if ! /usr/bin/tar -xzf "$HERE/runtime.tar.gz" -C "$NEW"; then
      echo "Setting up did not work. Please send a photo of this window to your teachers."
      rm -rf "$NEW"
      read -r -p "Press Return to close this window. " _
      exit 1
    fi
    strip_quarantine "$NEW"  # whatever the system's tar did with the flag
    touch "$NEW/ready-$PKG"  # last: a failed or interrupted unpack leaves no marker, so the next start unpacks again
  else
    echo "Finishing the setup of the course tools..."
  fi
  rm -rf "$RT"
  mv "$NEW" "$RT"
fi

# An installation that already has the flag (made before this check existed, or unpacked by a tar that passed it on): one native file tells
if "$XATTR" -p com.apple.quarantine "$RT/python/bin/python3" >/dev/null 2>&1; then
  strip_quarantine "$RT"
fi

[ -n "$HS_SETUP_ONLY" ] && exit 0  # the build's own check of this script stops here
"$RT/python/bin/python3" -s "$HERE/launcher/start.py" "$RT" "$@"
