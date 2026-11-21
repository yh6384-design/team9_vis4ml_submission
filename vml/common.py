"""Small helpers shared by all stages."""
from __future__ import annotations

import getpass
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import params
from .paths import REPO, out_root


def log(stage: str, msg: str) -> None:
    print(f"[{stage}] {msg}", flush=True)


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class NpEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, Path):
            return str(o)
        return super().default(o)


def write_json(path: Path, obj, indent=1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent, cls=NpEncoder)


def read_json(path: Path):
    with open(path) as f:
        return json.load(f)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "no-git"


def write_manifest(stage: str, inputs: dict, outputs: list, notes: dict | None = None) -> None:
    """Write VML_OUT/<stage>/_run.json: who ran it, when, with which inputs (sha1) and parameters.

    This is how we can tell, months later, which numbers in the paper came from which run.
    """
    d = out_root() / stage
    man = {
        "stage": stage,
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_by": getpass.getuser(),
        "machine": platform.node(),
        "python": sys.version.split()[0],
        "git_commit": git_commit(),
        "inputs": {k: {"path": str(v), "sha1": sha1(Path(v)) if Path(v).is_file() else "dir"} for k, v in inputs.items()},
        "outputs": [str(o) for o in outputs],
        "params": {k: getattr(params, k) for k in dir(params) if k.isupper()},
        "notes": notes or {},
    }
    write_json(d / "_run.json", man)


def need(path: Path, made_by: str) -> Path:
    if not Path(path).exists():
        raise SystemExit(f"Missing input {path}\n  -> run {made_by} first (see run_all.sh for the run order).")
    return Path(path)


def read_csv(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, **kw)
