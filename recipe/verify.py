"""Checks V1-V11 for the built app. Usage: verify.py [V2 V3 ...]  (default: all)."""
import contextlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "target"
APP = TARGET / "dist" / "drum2midi.app"
DMG = TARGET / "drum2midi.dmg"
FIXTURE = TARGET / "fixture.wav"
LOGS = TARGET / "logs"
VPY = TARGET / "venv" / "bin" / "python"
SHIM = TARGET / "shim" / "python"
NO_NETWORK = "(version 1)(allow default)(deny network*)"
FROZEN_ENV = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin", "QT_QPA_PLATFORM": "offscreen"}


class Fail(Exception):
    pass


def exe(app=APP):
    return app / "Contents" / "MacOS" / "drum2midi"


def root(app=APP):
    return app / "Contents" / "Frameworks" / "app"


def sh(cmd, env=None, timeout=1800, sandbox=False, cwd=None):
    if sandbox:
        cmd = ["sandbox-exec", "-p", NO_NETWORK, *cmd]
    r = subprocess.run(list(map(str, cmd)), env=env, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    with open(LOGS / "verify.log", "a") as fh:
        fh.write(f"\n$ {' '.join(map(str, cmd))}\n(exit {r.returncode})\n{r.stdout[-3000:]}{r.stderr[-3000:]}\n")
    return r


def note_count(mid):
    r = subprocess.run([str(VPY), "-c", "import pretty_midi,sys;m=pretty_midi.PrettyMIDI(sys.argv[1]);"
                        "print(sum(len(i.notes) for i in m.instruments))", str(mid)],
                       capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def expect_notes(r, mid):
    if r.returncode != 0:
        raise Fail(f"exit {r.returncode}: {r.stderr.strip().splitlines()[-1:] or r.stdout.strip().splitlines()[-1:]}")
    if not Path(mid).exists() or note_count(mid) == 0:
        raise Fail("no notes in MIDI")


def convert(device="cpu", extra=(), env=FROZEN_ENV, sandbox=False, app=APP, out="v.mid"):
    mid = TARGET / out
    mid.unlink(missing_ok=True)
    r = sh([exe(app), root(app) / "drum2midi.py", FIXTURE, "-o", mid, "--device", device, *extra],
           env=env, sandbox=sandbox)
    expect_notes(r, mid)
    return mid


def render(mid, env=FROZEN_ENV, sandbox=False):
    wav = TARGET / "v.wav"
    wav.unlink(missing_ok=True)
    r = sh([exe(), root() / "render_midi.py", mid, "-o", wav], env=env, sandbox=sandbox)
    if r.returncode != 0 or not wav.exists():
        raise Fail(f"render exit {r.returncode}")
    peak = subprocess.run([str(VPY), "-c", "import soundfile as sf,numpy as np,sys;"
                           "print(float(np.abs(sf.read(sys.argv[1])[0]).max()))", str(wav)],
                          capture_output=True, text=True).stdout.strip()
    if float(peak or 0) < 1e-4:
        raise Fail("silent wav")


def selftest(app=APP):
    r = sh([exe(app), "--selftest"], env=FROZEN_ENV, timeout=300)
    if r.returncode != 0 or "OK" not in r.stdout:
        raise Fail(f"selftest exit {r.returncode}")


def make_shim():
    SHIM.parent.mkdir(parents=True, exist_ok=True)
    SHIM.write_text(f'#!/bin/sh\nexec "{VPY}" -B "{REPO / "recipe" / "entry.py"}" "$@"\n')
    SHIM.chmod(0o755)


def v1():
    make_shim()
    env = {**os.environ, "DRUM2MIDI_EXE": str(SHIM), "QT_QPA_PLATFORM": "offscreen"}
    mid = TARGET / "v1.mid"
    mid.unlink(missing_ok=True)
    r = sh([SHIM, TARGET / "stage" / "app" / "drum2midi.py", FIXTURE, "-o", mid, "--device", "cpu"], env=env)
    expect_notes(r, mid)


def v2():
    convert()


def v3():
    convert(device="auto", out="v3.mid")


def v4():
    convert(extra=["--from-song"], out="v4.mid")


def v5():
    render(convert())


def v6():
    selftest()


def v7():
    mid = convert(sandbox=True)
    convert(extra=["--from-song"], sandbox=True, out="v7s.mid")
    render(mid, sandbox=True)


@contextlib.contextmanager
def read_only(path):
    subprocess.run(["chmod", "-R", "a-w", str(path)], check=True)
    try:
        yield
    finally:
        subprocess.run(["chmod", "-R", "u+w", str(path)], check=True)


def v8():
    with read_only(root()):
        convert()
        convert(extra=["--from-song"], out="v8s.mid")


def macho_files(app):
    for path in app.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with open(path, "rb") as fh:
                if fh.read(4) in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                    yield path


def v9():
    bad = []
    for path in macho_files(APP):
        for flag in ("-L", "-l"):
            out = subprocess.run(["otool", flag, str(path)], capture_output=True, text=True).stdout
            body = out.splitlines()[1:]
            lines = [ln for ln in body if "/opt/homebrew" in ln or "/usr/local" in ln or "/Users/" in ln]
            if flag == "-l":
                lines = [ln for ln in lines if "path " in ln]
            bad += [f"{path.name}: {ln.strip()}" for ln in lines]
    if bad:
        raise Fail(f"{len(bad)} host paths, first: {bad[0]}")
    convert(env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "QT_QPA_PLATFORM": "offscreen"})


def v10():
    r = sh(["codesign", "--verify", "--deep", "--strict", APP])
    if r.returncode != 0:
        raise Fail("codesign verify")
    if not DMG.exists() or sh(["hdiutil", "verify", DMG]).returncode != 0:
        raise Fail("hdiutil verify")
    mount = Path(tempfile.mkdtemp(prefix="d2m_mount_"))
    sh(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mount, DMG])
    try:
        selftest(mount / "drum2midi.app")
    finally:
        sh(["hdiutil", "detach", "-force", mount])


def du_mb(path):
    r = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True)
    return int(r.stdout.split()[0]) // 1024 if r.stdout else 0


def v11():
    print(f"app {du_mb(APP)} MB, dmg {du_mb(DMG)} MB")


CHECKS = {f"V{i}": fn for i, fn in enumerate((v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11), 1)}


def main(argv):
    LOGS.mkdir(parents=True, exist_ok=True)
    failed = False
    for name in argv or CHECKS:
        try:
            CHECKS[name]()
            print(f"{name} ✓", flush=True)
        except (Fail, subprocess.TimeoutExpired, OSError) as exc:
            failed = True
            print(f"{name} ✗ {exc}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
