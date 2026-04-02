"""Simple utilities to load historical cleaned tenancy CSVs.

This module provides small, focused functions to load all cleaned CSV
snapshots from the `data/` folder, parse the timestamp embedded in the
filename (when present) and return per-source `pandas.DataFrame` objects.

Usage examples:
    from data_loader import load_s_dk_clean_data, load_kab_clean_data
    s_df = load_s_dk_clean_data('data')
    kab_df = load_kab_clean_data('data')

The module keeps the implementation generic and exposes two thin wrappers
for the two sources (`s_dk` and `kab`) to avoid duplication. A convenience
helper `load_all_clean_data` returns a dict with both DataFrames (not a
single concatenated frame) to avoid mixing different schemas.
"""
from __future__ import annotations

import glob
import os
import re
from datetime import datetime
from typing import Callable, Optional, Union

import pandas as pd
from pandas._libs.tslibs.nattype import NaTType

_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})")


def _parse_timestamp_from_filename(path: str) -> Union[pd.Timestamp, NaTType]:
    """Extract a timestamp from `path` using the expected filename pattern.

    If no timestamp is present the function falls back to the file's
    modification time. Returns `pd.NaT` if neither are available.
    """
    name = os.path.basename(path)
    m = _TIMESTAMP_RE.search(name)
    if m:
        try:
            return pd.to_datetime(m.group(1), format="%Y-%m-%d_%H-%M-%S")
        except Exception:
            return pd.to_datetime(m.group(1), errors="coerce")

    try:
        ts = datetime.fromtimestamp(os.path.getmtime(path))
        return pd.to_datetime(ts)
    except Exception:
        return pd.NaT


def _load_and_tag(
    pattern: str,
    source: Optional[str] = None,
    parse_time_fn: Callable[[str], Union[pd.Timestamp, NaTType]] = _parse_timestamp_from_filename,
    read_csv_kwargs: Optional[dict] = None,
) -> pd.DataFrame:
    """Load all files matching `pattern`, tag them and concatenate.

    - `pattern` is a glob-style path (e.g. 'data/s_dk_tenancies*_clean.csv').
    - `source` when provided is written into a `source` column.
    - `snapshot_time` column is added (parsed from filename or file mtime).
    - `source_file` column contains the original filename.
    """
    files = sorted(glob.glob(pattern))
    if not files:
        return pd.DataFrame()

    dfs = []
    for p in files:
        try:
            df = pd.read_csv(p, **(read_csv_kwargs or {}))
        except Exception:
            # skip files that can't be read but continue with others
            continue

        # make a copy before inserting columns to avoid modifying callers' data
        df = df.copy()
        snapshot = parse_time_fn(p)
        df.insert(0, "snapshot_time", snapshot)
        if source is not None:
            df.insert(1, "source", source)
        df.insert(2, "source_file", os.path.basename(p))
        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True, sort=False)


def load_s_dk_clean_data(data_dir: str = "data") -> pd.DataFrame:
    """Load all cleaned s.dk tenancy snapshots from `data_dir`.

    Matches files like: `data/s_dk_tenancies_[%Y-%m-%d_%H-%M-%S]_clean.csv`.
    """
    pattern = os.path.join(data_dir, "s_dk_tenancies*_clean.csv")
    return _load_and_tag(pattern, source="s_dk")


def load_kab_clean_data(data_dir: str = "data") -> pd.DataFrame:
    """Load all cleaned KAB tenancy snapshots from `data_dir`.

    Matches files like: `data/kab_tenancies_[%Y-%m-%d_%H-%M-%S]_clean.csv`.
    """
    pattern = os.path.join(data_dir, "kab_tenancies*_clean.csv")
    return _load_and_tag(pattern, source="kab")


def load_all_clean_data(data_dir: str = "data") -> dict:
    """Load cleaned snapshots from both sources and return separate frames.

    Returns a dict with keys `'s_dk'` and `'kab'` mapping to each
    `pandas.DataFrame`. This deliberately avoids concatenating the two
    sources because they have different schemas.
    """
    return {
        "s_dk": load_s_dk_clean_data(data_dir),
        "kab": load_kab_clean_data(data_dir),
    }


__all__ = [
    "load_s_dk_clean_data",
    "load_kab_clean_data",
    "load_all_clean_data",
]
