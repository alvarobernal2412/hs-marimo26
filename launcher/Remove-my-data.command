#!/bin/bash
# Starts the notebooks again after removing your saved data in a notebook. Close the window of a running start first.
exec "$(dirname "$0")/Start.command" --remove-data
