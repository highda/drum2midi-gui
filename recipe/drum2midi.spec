import ast
import importlib.util
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

repo = Path(SPECPATH).parent
stage = repo / "target" / "stage" / "app"
icon = repo / "target" / "icon.icns"

def staged_imports():
    local = {f.stem for f in stage.glob("*.py*")}
    names = set()
    for src in [*stage.glob("*.py"), *stage.glob("*.pyw")]:
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.add(node.module)
                names.update(f"{node.module}.{a.name}" for a in node.names if node.module.startswith("PySide6"))
    keep = set()
    for name in names:
        top = name.split(".")[0]
        if top in local or top in sys.stdlib_module_names:
            continue
        try:
            if importlib.util.find_spec(top):
                keep.add(name)
        except (ImportError, ValueError, AttributeError):
            continue
    return sorted(keep)


datas, binaries, hiddenimports = [(str(stage), "app")], [], staged_imports()
for pkg in ("audio_separator", "adtof_pytorch", "librosa", "pretty_midi", "onnxruntime", "sklearn",
            "samplerate", "ml_collections", "rotary_embedding_torch", "onnx2torch", "diffq",
            "audioread", "soxr", "lazy_loader", "numba", "llvmlite"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

excludes = ["tkinter", "matplotlib", "IPython", "pytest", "PySide6.QtWebEngineCore",
            "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore",
            "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts", "PySide6.QtDataVisualization",
            "PySide6.QtPdf", "PySide6.QtDesigner", "PySide6.QtSql", "PySide6.QtTest"]

a = Analysis([str(repo / "recipe" / "entry.py")], pathex=[str(stage)], datas=datas, binaries=binaries,
             hiddenimports=hiddenimports, excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="drum2midi", console=False,
          argv_emulation=False, target_arch="arm64", icon=str(icon))
coll = COLLECT(exe, a.binaries, a.datas, name="drum2midi")
app = BUNDLE(coll, name="drum2midi.app", icon=str(icon), bundle_identifier="local.drum2midi-gui",
             info_plist={
                 "CFBundleName": "drum2midi",
                 "CFBundleDisplayName": "drum2midi",
                 "CFBundleShortVersionString": "1.0",
                 "NSHighResolutionCapable": True,
                 "LSMinimumSystemVersion": "12.0",
                 "NSMicrophoneUsageDescription": "Qt multimedia may probe audio capture devices; nothing is recorded.",
             })
