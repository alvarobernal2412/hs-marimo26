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
    touch "$NEW/ready-$PKG"  # last: a failed or interrupted unpack leaves no marker, so the next start unpacks again
  else
    echo "Finishing the setup of the course tools..."
  fi
  rm -rf "$RT"
  mv "$NEW" "$RT"
fi
"$RT/python/bin/python3" -s "$HERE/launcher/start.py" "$RT" "$@"
