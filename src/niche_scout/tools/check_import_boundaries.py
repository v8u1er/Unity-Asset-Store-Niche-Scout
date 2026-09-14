"""Run the repository import-boundary validator as a package module."""

from pathlib import Path


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[3] / "tools" / "check_import_boundaries.py"
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), {"__name__": "__main__", "__file__": str(source)})
