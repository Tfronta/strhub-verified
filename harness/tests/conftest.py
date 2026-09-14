import pathlib
import sys

HARNESS = pathlib.Path(__file__).resolve().parents[1]
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
