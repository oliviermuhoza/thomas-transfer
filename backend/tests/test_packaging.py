"""Vercel installs the root requirements.txt; it must cover the backend's."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _packages(path):
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = line
        for separator in ("==", ">=", "<=", "~=", ">", "<", "["):
            name = name.split(separator, 1)[0]
        names.add(name.strip().lower())
    return names


def test_root_requirements_cover_backend_requirements():
    root = _packages(ROOT / "requirements.txt")
    backend = _packages(ROOT / "backend" / "requirements.txt")
    missing = backend - root
    assert not missing, (
        f"add {sorted(missing)} to the root requirements.txt; Vercel installs "
        "that file and the app fails at import without these packages"
    )
