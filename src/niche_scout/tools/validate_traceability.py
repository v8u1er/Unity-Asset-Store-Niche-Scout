"""Run the repository traceability validator as a package module."""

from pathlib import Path


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[3] / "tools" / "validate_traceability.py"
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), {"__name__": "__main__", "__file__": str(source)})
