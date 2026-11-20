#!/bin/bash
# Starts the notebooks again and asks the consent question again. Close the window of a running start first.
exec "$(dirname "$0")/Start.command" --consent
