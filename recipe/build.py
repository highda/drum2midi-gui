"""Build drum2midi.app and drum2midi.dmg from the pinned upstream submodule."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "target"
UPSTREAM = REPO / "upstream"
LOGS = TARGET / "logs"
VENV = TARGET / "venv"
VPY = VENV / "bin" / "python"

ADTOF_URL = "https://github.com/xavriley/ADTOF-pytorch.git"
ADTOF_SHA = "85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9"
APP_DEPS = ["scipy", "librosa", "soundfile", "pretty_midi", "mido", "onnxruntime",
            "scikit-learn", "tqdm", "PySide6", "pillow", "pyyaml", "audioread"]


def phase(name):
    print(f"phase {name}", flush=True)


def run(cmd, log, **kw):
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{log}.log", "ab") as fh:
        fh.write(f"\n$ {' '.join(map(str, cmd))}\n".encode())
        fh.flush()
        subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=True, **kw)


def pip(*args, log="env"):
    run([str(VPY), "-m", "pip", "install", *args], log)


def env():
    phase("env")
    if not VPY.exists():
        run([sys.executable, "-m", "venv", str(VENV)], "env")
    pip("-U", "pip", "wheel", "setuptools", "cython", "numpy")
    pip("torch")
    pip("diffq", "--no-build-isolation")
    pip("audio-separator")
    pip(*APP_DEPS)
    src = TARGET / "src" / "ADTOF-pytorch"
    if not src.exists():
        run(["git", "clone", "-q", ADTOF_URL, str(src)], "env")
    run(["git", "-C", str(src), "checkout", "-q", ADTOF_SHA], "env")
    pip(str(src))
    pip("pyinstaller", "imageio-ffmpeg")
    freeze = subprocess.run([str(VPY), "-m", "pip", "freeze"], capture_output=True, text=True, check=True)
    (TARGET / "freeze.txt").write_text(freeze.stdout)
    run([str(VPY), "-c", "import torch, librosa, audio_separator, adtof_pytorch, diffq, "
         "PySide6.QtMultimedia"], "env")


SOUNDFONT_URL = ("https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/"
                 "MuseScore_General.sf3")
CHECKSUMS = REPO / "recipe" / "checksums.txt"
STAGE = TARGET / "stage"
ROOT_STAGE = STAGE / "app"
FIXTURE = TARGET / "fixture.wav"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def checksums():
    table = {}
    if CHECKSUMS.exists():
        for line in CHECKSUMS.read_text().splitlines():
            if line.strip():
                digest, key = line.split(None, 1)
                table[key.strip()] = digest
    return table


def check(key, path):
    """Enforce a recorded hash; record it on first sight."""
    table, digest = checksums(), sha256(path)
    if key not in table:
        with open(CHECKSUMS, "a") as fh:
            fh.write(f"{digest}  {key}\n")
    elif table[key] != digest:
        raise SystemExit(f"checksum mismatch for {key}: {digest} != {table[key]}")


def fetch(url, dest, key):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["curl", "-fsSL", "-o", str(dest), url], "assets")
    check(key, dest)


def apply_patches():
    for patch in sorted((REPO / "recipe" / "patches").glob("*.patch")):
        run(["patch", "-p1", "-d", str(ROOT_STAGE), "-i", str(patch)], "stage")


def stage():
    phase("stage")
    if ROOT_STAGE.exists():
        keep = {ROOT_STAGE / "uvr", ROOT_STAGE / "tools", ROOT_STAGE / "bin"}
        for child in ROOT_STAGE.iterdir():
            if child not in keep:
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    ROOT_STAGE.mkdir(parents=True, exist_ok=True)
    for src in [*UPSTREAM.glob("*.py"), *UPSTREAM.glob("*.pyw")]:
        shutil.copy2(src, ROOT_STAGE / src.name)
    (ROOT_STAGE / "models").mkdir(exist_ok=True)
    for pkl in (UPSTREAM / "models").glob("*.pkl"):
        shutil.copy2(pkl, ROOT_STAGE / "models" / pkl.name)
    (ROOT_STAGE / "docs").mkdir(exist_ok=True)
    for name in ("drum2midi.ico", "logo_256.png"):
        shutil.copy2(UPSTREAM / "docs" / name, ROOT_STAGE / "docs" / name)
    apply_patches()


def ffmpeg():
    phase("ffmpeg")
    exe = next((VENV / "lib").glob("python3*/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-*"))
    dest = ROOT_STAGE / "bin" / "ffmpeg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, dest)
    dest.chmod(0o755)
    check(f"ffmpeg:{exe.name}", dest)
    libs = subprocess.run(["otool", "-L", str(dest)], capture_output=True, text=True, check=True).stdout
    bad = [ln for ln in libs.splitlines()[1:] if "/usr/lib" not in ln and "/System" not in ln]
    if bad:
        raise SystemExit(f"ffmpeg is not static: {bad}")


def macho_files(root):
    for path in Path(root).rglob("*"):
        if path.is_file() and not path.is_symlink():
            with open(path, "rb") as fh:
                if fh.read(4) in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                    yield path


def fluidsynth():
    phase("fluidsynth")
    tools = ROOT_STAGE / "tools"
    fetch(SOUNDFONT_URL, TARGET / "downloads" / "MuseScore_General.sf3", "MuseScore_General.sf3")
    tools.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET / "downloads" / "MuseScore_General.sf3", tools / "MuseScore_General.sf3")
    fs = tools / "fluidsynth"
    shutil.rmtree(fs, ignore_errors=True)
    (fs / "libs").mkdir(parents=True)
    prefix = subprocess.run(["brew", "--prefix", "fluid-synth"], capture_output=True, text=True,
                            check=True).stdout.strip()
    shutil.copy2(Path(prefix) / "bin" / "fluidsynth", fs / "fluidsynth")
    (fs / "fluidsynth").chmod(0o755)
    run(["dylibbundler", "-od", "-b", "-x", str(fs / "fluidsynth"), "-d", str(fs / "libs"),
         "-p", "@executable_path/libs/"], "assets")
    for path in macho_files(fs):
        run(["codesign", "--force", "-s", "-", str(path)], "assets")
    for path in macho_files(fs):
        out = subprocess.run(["otool", "-L", str(path)], capture_output=True, text=True, check=True).stdout
        if "/opt/homebrew" in out or "/usr/local" in out:
            raise SystemExit(f"unrelocated library path in {path}")


def make_fixture():
    if FIXTURE.exists():
        return
    code = ("import test_smoke; from pathlib import Path; test_smoke._tmp = Path(r'%s'); "
            "test_smoke.make_fixture()" % TARGET)
    run([str(VPY), "-B", "-c", code], "assets", cwd=UPSTREAM)


def child_env():
    return {**os.environ, "PATH": f"{ROOT_STAGE / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "DRUM2MIDI_WORK": str(TARGET / "work")}


def seed_models():
    phase("seed")
    make_fixture()
    for name, extra in (("uvr", []), ("from-song", ["--from-song"])):
        out = TARGET / f"seed_{name}.mid"
        run([str(VPY), str(ROOT_STAGE / "drum2midi.py"), str(FIXTURE), "-o", str(out),
             "--device", "cpu", *extra], "seed", cwd=ROOT_STAGE, env=child_env())
    models = ROOT_STAGE / "uvr" / "models"
    for path in sorted(p for p in models.rglob("*") if p.is_file()):
        check(f"uvr/{path.relative_to(models)}", path)


PHASES = {"env": env, "stage": stage, "ffmpeg": ffmpeg, "fluidsynth": fluidsynth, "seed": seed_models}


def main(argv):
    for name in argv or PHASES:
        PHASES[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
