"""Build drum2midi.app and drum2midi.dmg from the pinned upstream submodule."""
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
            "scikit-learn", "tqdm", "PySide6", "pillow", "pyyaml"]


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


def main(argv):
    env()


if __name__ == "__main__":
    main(sys.argv[1:])
