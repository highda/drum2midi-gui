"""Build drum2midi.app and drum2midi.dmg from the pinned upstream submodule."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "target"
UPSTREAM = REPO / "upstream"


def main(argv):
    raise SystemExit("not implemented")


if __name__ == "__main__":
    main(sys.argv[1:])
