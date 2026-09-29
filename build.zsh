#!/bin/zsh
# Thin wizard; all logic lives in recipe/build.py.
set -euo pipefail
cd "${0:A:h}"

FORMULAE=(python@3.12 fluid-synth dylibbundler create-dmg)
ARGS=()
for a in "$@"; do ARGS+=("$a"); done

[[ "$(uname -m)" == arm64 ]] || { echo "arm64 Mac required" >&2; exit 1; }
xcode-select -p >/dev/null 2>&1 || { echo "Install Xcode command-line tools: xcode-select --install" >&2; exit 1; }
command -v brew >/dev/null || {
  echo 'Install Homebrew: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' >&2
  exit 1
}

brew install "${FORMULAE[@]}"
git submodule update --init
exec "$(brew --prefix python@3.12)/bin/python3.12" recipe/build.py "${ARGS[@]}"
