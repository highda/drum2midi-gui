# drum2midi-gui

Build recipe: turns the pinned `upstream/` submodule (miraer/drum2midi) into a self-contained
arm64 `.app` and `.dmg` under `target/` (gitignored). macOS arm64 only, local builds only, no CI.

## Rules

- Never edit `upstream/`. Prefer runtime monkeypatching in `recipe/entry.py`; last resort is a
  patch (<= 20 lines, documented in `recipe/patches/README`) applied to the staged copy.
- Never commit anything under `target/`, weights, upstream code, or built artifacts. Never push
  or add a remote. No sudo.
- Every download is verified against `recipe/checksums.txt`; a missing or mismatched hash is a build error.
- The app must run offline, out of the box, and never write into its own bundle
  (state lives in `~/Library/Application Support/drum2midi`).
- Recipe code: Python 3.12-clean, small functions, no comment noise. `build.zsh` stays a thin wizard;
  logic lives in `recipe/build.py`. Everything user-facing is English.
- Long build steps log to `target/logs/<phase>.log`; read `tail -n 30` or grep, not the whole log.
- On failure: read the log, change one thing, retry. Same error four times: write
  `target/logs/BLOCKED.md` and take the next fallback.
- Commit locally with small imperative subjects.

## Layout

- `build.zsh` wizard (arm64, Xcode CLT, brew formulae, submodule) then `recipe/build.py`
- `recipe/`: `build.py` (venv, deps, fetch, stage, freeze, prune, sign, dmg), `entry.py` (frozen entry
  and mini-interpreter for `-c` / `-m` / `script.py`), `verify.py` (checks V1-V11), `drum2midi.spec`,
  `checksums.txt`, `patches/`
