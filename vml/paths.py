"""Where inputs live and where outputs go.

Two environment variables control everything:

  VML_CORPUS  the raw corpus: profile_corpus_v2.zip OR the unzipped profile_corpus/ folder.
              Default: ../data/profile_corpus_v2.zip next to the repo, then profile_corpus/share/profile_corpus_v2.zip.
  VML_OUT     the folder that receives every output. Default: <repo>/outputs (ignored by git).

Stage outputs go to VML_OUT/<stage>/ (for example VML_OUT/models/predictions.csv).
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# inputs that are already committed in the repo (built by the earlier stages)
EPISODES = REPO / "episode_table" / "output" / "episodes.csv"
EPISODES_TARGET = REPO / "episode_table" / "output" / "episodes_target.csv"


def out_root() -> Path:
    p = Path(os.environ.get("VML_OUT", REPO / "outputs")).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def stage_dir(stage: str) -> Path:
    p = out_root() / stage
    p.mkdir(parents=True, exist_ok=True)
    return p


def _corpus_candidates():
    env = os.environ.get("VML_CORPUS")
    if env:
        yield Path(env).expanduser()
    yield REPO.parent / "data" / "profile_corpus_v2.zip"
    yield REPO.parent / "data" / "profile_corpus"
    yield REPO / "profile_corpus" / "share" / "profile_corpus_v2.zip"


def corpus_dir(required: bool = False) -> Path | None:
    """Return the unzipped profile_corpus folder (unzipping once into <repo>/_corpus_cache if needed), or None."""
    for c in _corpus_candidates():
        if c.is_dir() and (c / "profile_index.csv").exists():
            return c
        if c.is_dir() and (c / "profile_corpus" / "profile_index.csv").exists():
            return c / "profile_corpus"
        if c.is_file() and c.suffix == ".zip":
            work = REPO / "_corpus_cache"            # local, git-ignored; kept outside VML_OUT
            target = work / "profile_corpus"
            if not (target / "profile_index.csv").exists():
                work.mkdir(parents=True, exist_ok=True)
                print(f"[paths] unzipping {c} -> {work} (one time)")
                with zipfile.ZipFile(c) as z:
                    z.extractall(work)
            return target
    if required:
        raise SystemExit("Raw corpus not found. Set VML_CORPUS to profile_corpus_v2.zip or put it in ../data/.")
    return None
