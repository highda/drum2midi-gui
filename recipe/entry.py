"""Frozen entry point. Upstream re-invokes sys.executable as `exe script.py`, `exe -c code`
and `exe -m module`; this file is that interpreter, and starts the window otherwise."""
import multiprocessing
import os
import runpy
import sys
from pathlib import Path


def app_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app"
    default = Path(__file__).resolve().parent.parent / "target" / "stage" / "app"
    return Path(os.environ.get("DRUM2MIDI_ROOT", default))


def user_dir():
    path = Path.home() / "Library" / "Application Support" / "drum2midi"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_code(code, args):
    sys.argv = ["-c", *args]
    exec(compile(code, "<string>", "exec"), {"__name__": "__main__"})


def run_module(name, args):
    sys.argv = [name, *args]
    runpy.run_module(name, run_name="__main__", alter_sys=True)


def run_script(path, args):
    sys.argv = [path, *args]
    sys.path.insert(0, str(Path(path).resolve().parent))
    runpy.run_path(path, run_name="__main__")


def load_gui(root):
    gui = runpy.run_path(str(root / "drum2midi_gui.pyw"), run_name="drum2midi_gui")
    # run_path hands back a copy of the globals; the functions read the originals.
    gui["main"].__globals__["SETTINGS"] = user_dir() / "gui_settings.json"
    return gui


def selftest(root):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QEventLoop, QTimer
    gui = load_gui(root)
    app = gui["make_app"]([sys.argv[0]])
    win = gui["Window"]()
    win.show()
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec()
    settings = gui["main"].__globals__["SETTINGS"]
    win._save_settings()
    if user_dir() not in settings.parents or not settings.exists():
        print(f"FAIL settings path {settings}")
        return 1
    print(f"OK {settings}")
    win.close()
    app.quit()
    return 0


def main():
    multiprocessing.freeze_support()
    if os.environ.get("DRUM2MIDI_EXE"):
        sys.executable = os.environ["DRUM2MIDI_EXE"]
    root = app_root()
    os.environ["PATH"] = os.pathsep.join([str(root / "bin"), os.environ.get("PATH", "")])
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("DRUM2MIDI_WORK", str(user_dir() / "work"))
    args = sys.argv[1:]
    if args[:1] == ["-c"]:
        return run_code(args[1], args[2:])
    if args[:1] == ["-m"]:
        return run_module(args[1], args[2:])
    if args and args[0].endswith((".py", ".pyw")):
        return run_script(args[0], args[1:])
    if args[:1] == ["--selftest"]:
        sys.exit(selftest(root))
    sys.argv = [sys.argv[0], *[a for a in args if not a.startswith("-psn")]]
    load_gui(root)["main"]()


if __name__ == "__main__":
    main()
