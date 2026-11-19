"""Downloading tools into a per-user folder: the projects' official builds, checked against
a pinned SHA-256 before anything is unpacked. No admin rights, nothing outside that folder."""
import hashlib
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from . import term


def data_dir():
    """Per-user folder for the tools boardsim installs."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "boardsim"


def fetch(url, sha256, dest, executables=()):
    """Download url, check it, unpack it (zip or tarball) into dest, replacing what's there.
    An archive with a single top folder is unpacked without it. `executables` (paths in
    dest) get their executable bit back, which zip files don't keep."""
    name = url.rsplit("/", 1)[-1]
    data_dir().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data_dir()) as tmp:
        archive = Path(tmp) / name
        print(f"Downloading {term.path(url)}")
        h = hashlib.sha256()
        with urllib.request.urlopen(url) as r, open(archive, "wb") as f:
            total, done = int(r.headers.get("Content-Length", 0)), 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 1e6:5.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
        if h.hexdigest() != sha256:
            raise SystemExit(f"Checksum mismatch for {name}: download corrupted or changed. Nothing installed.")

        unpacked = Path(tmp) / "unpacked"
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(unpacked)
        else:
            with tarfile.open(archive) as t:
                kw = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
                t.extractall(unpacked, **kw)
        entries = list(unpacked.iterdir())
        root = entries[0] if len(entries) == 1 and entries[0].is_dir() else unpacked
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(root), str(dest))

    for exe in executables:
        p = dest / exe
        if p.exists() and sys.platform != "win32":
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest
