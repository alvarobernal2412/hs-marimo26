#!/bin/bash
cd "$(dirname "$0")"
./python/bin/python3 -s ./launcher/start.py "$PWD" "$@"
