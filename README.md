# drum2midi-gui

A local build recipe that turns [miraer/drum2midi](https://github.com/miraer/drum2midi)
(pinned as the `upstream/` submodule) into a self-contained Apple Silicon `drum2midi.app`
and `.dmg`. The built app needs nothing installed on the Mac that runs it: no Homebrew,
Python, ffmpeg or network.

> **Personal use only. Do not redistribute the built app or dmg.**
> It bundles components (ADTOF weights CC BY-NC-SA 4.0, ADTOF-pytorch with no licence file,
> and others; see `NOTICE`) that may not be redistributed. This repo holds only the recipe.

## Build

```
git clone --recurse-submodules <this repo>
./build.zsh            # --yes, --clean, --skip-verify
```

Requires an arm64 Mac, Xcode command-line tools and Homebrew. Output lands in `target/`
(gitignored): `target/dist/drum2midi.app`, `target/drum2midi.dmg`, logs in `target/logs/`.

If you copy the app to another Mac, macOS will quarantine it:
`xattr -dr com.apple.quarantine drum2midi.app`, or right-click, Open.

Scope: macOS arm64, MDX23C separator, ADTOF transcriber, `--from-song`, MIDI playback / A-B.
Not included: LarsNet, DrumSep, the `hybrid` separator, benchmark and training scripts.
