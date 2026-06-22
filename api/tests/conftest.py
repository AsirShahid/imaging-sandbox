"""Make the ``app`` package importable when running ``pytest`` from anywhere."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
