#!/bin/bash
# The runtime (Python and the notebooks) is one archive next to this file. It is unpacked once with the Mac's own tar.
cd "$(dirname "$0")"
HERE="$PWD"
RT="$HOME/Library/Application Support/hs-marimo26/runtime"
PKG="$(cat package-id.txt)"
if [ ! -e "$RT/ready-$PKG" ]; then
  echo "Setting up the course tools. This takes a minute or two the first time, please wait..."
  rm -rf "$RT"
  mkdir -p "$RT"
  if ! /usr/bin/tar -xzf "$HERE/runtime.tar.gz" -C "$RT"; then
    echo "Setting up did not work. Please send a photo of this window to your teachers."
    read -r -p "Press Return to close this window. " _
    exit 1
  fi
  touch "$RT/ready-$PKG"  # last: a failed or interrupted unpack leaves no marker, so the next start unpacks again
fi
"$RT/python/bin/python3" -s "$HERE/launcher/start.py" "$RT" "$@"
