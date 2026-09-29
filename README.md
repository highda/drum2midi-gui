# drum2midi-gui

A local **build recipe** that turns [miraer/drum2midi](https://github.com/miraer/drum2midi)
(pinned as the `upstream/` submodule) into a **self-contained Apple Silicon `drum2midi.app`
and `.dmg`**. The finished app needs nothing on the Mac that runs it: no Homebrew, Python,
ffmpeg, FluidSynth, compiler or network connection. Only the machine that *builds* it needs tools.

> **Personal use only. Do not redistribute the built app or dmg.**
> The bundle contains components whose licences forbid it (ADTOF weights are CC BY-NC-SA 4.0,
> ADTOF-pytorch has no licence file, and others; see [`NOTICE`](NOTICE)). This repository holds
> only the recipe, so it is safe to publish. What the recipe produces is not.

## What this is, and is not

- It **is** a script that builds the app on your own machine from original sources, the same way
  upstream's own `setup_env.py` would set up a development environment.
- It is **not** a download. There is no release, no prebuilt binary and no weights in this repo.
- It is **not** a fork. `upstream/` is an unmodified git submodule pinned to one commit. Where
  upstream needs adapting for a bundle, the recipe does it at runtime or with a tiny patch applied to a
  *staged copy* (see [How it works](#how-it-works)).

## What the app does

The app is upstream's window and command-line tools, frozen into a bundle:

- Converts a drum recording to General MIDI (MDX23C stem separation, ADTOF onset transcription,
  learned velocity and pedal models).
- `--from-song`: pulls the drums out of a full mix first (htdemucs).
- Plays the original, the MIDI, or an A/B of both (FluidSynth with the MuseScore General soundfont).

Not included in v1: LarsNet (563 MB, CC BY-NC, Google Drive download), DrumSep (legacy), the `hybrid`
separator, and the benchmark and training scripts.

## Requirements (build machine)

- An **Apple Silicon** Mac (arm64) on macOS 12 or later. Intel, universal2 and Windows are out of scope.
- Xcode command-line tools: `xcode-select --install`
- [Homebrew](https://brew.sh)
- About 6 GB of free disk for `target/` (measured: venv 2.5 GB, app 1.6 GB, dmg 0.9 GB, stage 0.6 GB), plus
  Homebrew's own footprint, and a network connection for the build (the models alone are about 520 MB). A fresh, from-scratch build has not been timed; expect it to
  take a while, mostly downloads and verification.

The wizard installs the Homebrew formulae it needs (`python@3.12`, `fluid-synth`, `dylibbundler`,
`create-dmg`).

## Build

```sh
git clone --recurse-submodules https://github.com/highda/drum2midi-gui.git
cd drum2midi-gui
./build.zsh
```

| Flag | Effect |
|---|---|
| `--yes` | No prompts (skips the "copy to /Applications?" question). |
| `--clean` | Delete `target/` first and build from scratch. |
| `--skip-verify` | Build and package, skip the V1-V11 verification run. |

The wizard refuses anything that is not arm64, checks for the Xcode tools and Homebrew, installs the
formulae, runs `git submodule update --init`, then hands over to `recipe/build.py`. When it finishes it
prints the paths and sizes of the outputs and the licensing banner.

### Outputs

Everything lands in `target/` (gitignored):

| Path | What |
|---|---|
| `target/dist/drum2midi.app` | The app, ad-hoc signed |
| `target/drum2midi.dmg` | Compressed disk image containing the app and an Applications link |
| `target/logs/` | One log per phase, plus `verify.log` |
| `target/freeze.txt` | `pip freeze` of the build environment |

### Running single phases

`recipe/build.py` takes phase names, which is useful when iterating:

```sh
target/venv/bin/python recipe/build.py stage ffmpeg      # re-stage upstream and ffmpeg
target/venv/bin/python recipe/build.py freeze finish     # re-freeze, prune, sign
target/venv/bin/python recipe/build.py package           # rebuild the dmg
target/venv/bin/python recipe/verify.py V2 V7            # run selected checks
```

Phases, in order: `env`, `stage`, `ffmpeg`, `fluidsynth`, `seed`, `freeze`, `finish`, `package`, `verify`.

## Using the app

Open `drum2midi.app` from `target/dist/` (or mount the dmg and drag it to Applications). Drop a drum
clip on the window and press Convert.

- Settings and scratch files live in `~/Library/Application Support/drum2midi`, never inside the app.
  Playback renders are cached in the system temp directory.
- The app is ad-hoc signed and not notarized. An app you built yourself opens normally. If you copy it to
  another Mac it will be quarantined; clear that with
  `xattr -dr com.apple.quarantine drum2midi.app`, or right-click and choose Open.
- The same executable also works as a command-line tool:
  `drum2midi.app/Contents/MacOS/drum2midi <path>/drum2midi.py clip.wav -o out.mid` (the scripts sit in
  `Contents/Frameworks/app/`).

## How it works

**Staging.** Every top-level upstream `*.py` / `*.pyw`, the two learned models (`models/*.pkl`) and the
GUI's two icon files are copied to `target/stage/app/`, which becomes upstream's `ROOT` inside the bundle.
Then `tools/` (soundfont, FluidSynth), `bin/` (ffmpeg) and `uvr/models/` are added.

**One executable, three roles.** Upstream re-invokes `sys.executable` as `exe script.py`, `exe -c code`
and `exe -m module`, and the GUI and separator both run that way. In a frozen app `sys.executable` is the
app's own launcher, so `recipe/entry.py` is a small interpreter: it dispatches those three forms (after
stripping the interpreter flags `multiprocessing` adds), and otherwise starts the GUI with its settings
redirected to the user directory. `--selftest` builds the window offscreen and exits.

**Offline by construction.** `audio-separator` downloads models and refreshes metadata from GitHub on
first use. The build runs one real separation and one `--from-song` run on a synthetic fixture with the
staged `uvr/models` directory as its model dir, then ships that directory whole.

**FluidSynth** is copied from Homebrew and relocated with `dylibbundler` so no `/opt/homebrew` path
survives; every Mach-O is re-signed ad hoc. **ffmpeg** is the static arm64 binary from the
`imageio-ffmpeg` wheel.

**Two small departures from stock upstream**, both outside the submodule:

- `recipe/patches/work-dir.patch`: `--from-song` wrote its drum stem to `ROOT/work`, inside the bundle. The
  patch, applied to the staged copy, reads `DRUM2MIDI_WORK` (set by the entry point to the user directory).
- Dependency pins the recipe adds: `diffq` is compiled from source (no arm64 wheel), `audioread` is added
  (audio-separator imports it without declaring it), and `samplerate` 0.2.4 replaces 0.1.0, whose bundled
  library is x86_64-only.

## Verification

`recipe/verify.py` runs eleven checks; the build runs them unless `--skip-verify` is given.

| # | Check |
|---|---|
| V1 | Unfrozen: the entry point drives a full conversion of a synthetic fixture (child processes included) |
| V2 | Frozen app converts the fixture on CPU to a MIDI with notes |
| V3 | Same with `--device auto` (MPS) |
| V4 | Frozen `--from-song` (htdemucs) |
| V5 | Frozen `render_midi.py` produces a non-silent wav |
| V6 | `--selftest`: window builds offscreen, settings path is under Application Support |
| V7 | V2, V4 and V5 under `sandbox-exec` with the network denied |
| V8 | V2 and V4 with the bundled `app/` tree made read-only |
| V9 | No Mach-O references `/opt/homebrew`, `/usr/local` or `/Users`; V2 under `env -i PATH=/usr/bin:/bin` |
| V10 | `codesign --verify --deep --strict`, `hdiutil verify`, and V6 run from the mounted dmg |
| V11 | Size report |

Not automated, and worth doing by hand after a build: audio playback (Original / MIDI / A-B), the look of
the window, drag and drop, and a conversion of a real song.

## Repository layout

```
build.zsh              wizard: arm64, Xcode tools, Homebrew, formulae, submodule, then recipe/build.py
recipe/
  build.py             venv, deps, fetch and verify, stage, freeze, prune, sign, dmg
  entry.py             frozen entry point and mini-interpreter
  verify.py            checks V1-V11
  drum2midi.spec       PyInstaller spec
  checksums.txt        sha256 of everything fetched (soundfont, ffmpeg, models)
  patches/             patches applied to the staged copy of upstream
upstream/              submodule -> miraer/drum2midi, pinned
NOTICE  LICENSE  CLAUDE.md
```

## Downloads and integrity

Everything fetched at build time is listed in [`NOTICE`](NOTICE) with its source and licence, and checked
against `recipe/checksums.txt`. For files with no versioned upstream (the soundfont, ffmpeg, model files)
the hash is recorded the first time it is fetched and enforced from then on, so a mismatch stops the
build. ADTOF-pytorch is pinned by git commit.

## Updating upstream

Bumping `upstream/` is a deliberate act: check out the new commit in the submodule, commit the pointer,
rebuild, and let the verification run judge it. `work-dir.patch` may need refreshing if the patched line
moves, and the pinned dependency notes above may change.

## Notes

- Build-time Python is 3.12 (Homebrew). Upstream supports 3.10-3.13; 3.13 is the fallback if a wheel is missing.
- Loading the learned models can print scikit-learn's `InconsistentVersionWarning`: they were pickled with
  1.9.0 and the build resolves 1.9.1. It is a warning only.
- No CI. A build of this size does not fit a free GitHub account, so builds are local by design.

## Licence

The recipe in this repository is MIT ([`LICENSE`](LICENSE)). That covers the recipe only: upstream
drum2midi is MIT, but the models and libraries the build fetches carry their own licences (see
[`NOTICE`](NOTICE) and upstream's `THIRD-PARTY-NOTICES.md`), which is why the built app is for personal
use on the machine that built it.
