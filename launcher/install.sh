#!/bin/bash
# Installs (or updates) the course tools on a Mac from the terminal:
#   curl -fsSL https://github.com/alvarobernal2412/hs-marimo26/releases/latest/download/install.sh | bash
# Everything is fetched by curl, never by a browser, so macOS puts no "downloaded from the internet" mark on it and shows no
# security dialog. The package goes to ~/hs-marimo26 and starts; later, double-click Start in that folder (or paste this line again).
# Overrides, for tests: HS_PACKAGE_URL (a zip's URL or a local file), HS_DEST (the folder), HS_ARCH (arm64 or x86_64),
# HS_NO_START=1 (install, do not start).

main() {
  local repo="alvarobernal2412/hs-marimo26"
  local dest="${HS_DEST:-$HOME/hs-marimo26}"
  local os arch url tmp

  arch="${HS_ARCH:-}"
  if [ -z "$arch" ]; then
    if [ "$(uname -s)" != "Darwin" ]; then
      echo "This installer is for a Mac. On Windows, see the instructions your teachers gave you."
      return 1
    fi
    # a terminal running under Rosetta says x86_64 even on an Apple-chip Mac: ask the hardware
    if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then arch="arm64"; else arch="$(uname -m)"; fi
  fi
  case "$arch" in
    arm64 | aarch64) os="macos-arm64" ;;
    x86_64) os="macos-x64" ;;
    *) echo "This Mac type ($arch) is not supported. Please tell your teachers."; return 1 ;;
  esac

  url="${HS_PACKAGE_URL:-}"
  if [ -z "$url" ]; then
    echo "Looking for the latest version of the course tools..."
    local tag
    # the public "latest release" page redirects to .../tag/<version>: no API call, so no rate limit for a whole classroom
    tag="$(curl -fsSL -o /dev/null -w '%{url_effective}' "https://github.com/$repo/releases/latest" | sed 's|.*/tag/||')"
    case "$tag" in
      v[0-9]*) ;;
      *) echo "Could not find the latest version. Check your internet connection and try again."; return 1 ;;
    esac
    url="https://github.com/$repo/releases/download/$tag/hs-marimo26-$tag-$os.zip"
  fi

  tmp="$(mktemp -d)" || return 1
  echo "Downloading the course tools (this can take a few minutes)..."
  if [ -f "$url" ]; then
    cp "$url" "$tmp/package.zip" || return 1
  elif ! curl -fL --progress-bar -o "$tmp/package.zip" "$url"; then
    echo "The download did not work. Check your internet connection and try again."
    rm -rf "$tmp"
    return 1
  fi

  mkdir -p "$dest" || return 1
  # only the package's own files are overwritten: anything else in the folder stays
  if ! /usr/bin/unzip -oq "$tmp/package.zip" -d "$dest"; then
    echo "Unpacking did not work. Please tell your teachers."
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "$tmp"
  chmod +x "$dest"/*.command 2>/dev/null

  echo
  echo "The course tools are in: $dest"
  if [ -n "${HS_NO_START:-}" ]; then return 0; fi
  echo "Starting them now. Next time, double-click Start in that folder."
  echo
  cd "$dest" || return 1
  # the script itself arrives on stdin when piped from curl: give the program the keyboard instead
  if [ -r /dev/tty ]; then exec ./Start.command </dev/tty; else exec ./Start.command; fi
}

# the whole file is read before anything runs, so a download cut short can never run half an installer
main "$@"
