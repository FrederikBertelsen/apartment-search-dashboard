"""Helpers to prepare data for the apartment dashboard.

Provides functions to load cleaned data (via `data_loader.load_all_clean_data`),
create stable apartment identifiers, deduplicate to the newest snapshot per
apartment, compute price-per-m2 estimates, prepare KAB history series, and
estimate ETA to queue position 0 using a simple linear trend.

This module is intentionally small and dependency-light (pandas, numpy).
"""
from __future__ import annotations

import hashlib
import re
from typing import Dict, Tuple, Any

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime

from data_loader import load_all_clean_data


def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _make_id_from_values(values: Tuple) -> str:
    s = "|".join(["" if v is None else str(v) for v in values])
    return _md5_text(s)


def _safe_token(s: Any, max_len: int = 30) -> str:
    """Return a filesystem/URL-safe, lowercased short token for display in IDs.

    Keeps only alphanumerics, dot, dash and underscore and replaces whitespace
    with underscore. Truncates to `max_len`.
    """
    if s is None:
        return ""
    try:
        if isinstance(s, float) and np.isnan(s):
            return ""
    except Exception:
        pass
    t = str(s).strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^a-z0-9_\-\.]", "", t)
    return t[:max_len]


def add_apartment_ids(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Add a deterministic `apartment_id` column to `df`.

    - For `kab` prefer `building_url` when present, else fallback to
      a combination of `addresses`, `room_count`, `area_min`, `area_max`.
    - For `s_dk` prefer `url`, else fallback to `address` + `area_m2`.
    """
    df = df.copy()
    if df.empty:
        df["apartment_id"] = pd.Series(dtype=str)
        return df

    if source == "kab":
        def _id_row(r):
            # prefer building_url for stability but include readable tokens
            bu = r.get("building_url", "")
            comp = _safe_token(r.get("company", ""))
            dept = _safe_token(r.get("department", ""))
            tenancy = r.get("tenancy_count", "")
            try:
                tenancy = str(int(tenancy)) if pd.notna(tenancy) and str(tenancy).strip() != "" else ""
            except Exception:
                tenancy = _safe_token(tenancy)

            if pd.notna(bu) and str(bu).strip():
                short_hash = _md5_text(str(bu))[:8]
            else:
                # fallback on address/room/area fingerprint
                short_hash = _md5_text(
                    f"{r.get('addresses','')}|{r.get('room_count','')}|{r.get('area_min','')}|{r.get('area_max','')}"
                )[:8]

            parts = [p for p in [comp, dept, (f"t{tenancy}" if tenancy else None), short_hash] if p]
            return "kab-" + "-".join(parts)

    elif source == "s_dk":
        def _id_row(r):
            # Use address + area + building_name + ranking fingerprint so each
            # apartment becomes its own id (stable short hash for readability).
            addr = r.get("address", "")
            area = r.get("area_m2", "")
            bname = r.get("building_name", "")
            rank = r.get("ranking", "")
            if pd.notna(addr) and str(addr).strip():
                fp = f"{addr}|{area}|{bname}|{rank}"
                short = _md5_text(fp)[:8]
                token = _safe_token(bname, max_len=20) or "sdk"
                return f"sdk-{token}-{short}"
            # fallback to url hash when address missing
            url = r.get("url", "")
            if pd.notna(url) and str(url).strip():
                return f"sdk-{_md5_text(str(url))[:8]}"
            return f"sdk-{_make_id_from_values((bname, addr, area, rank))}"

    else:
        def _id_row(r):
            return _make_id_from_values(tuple(r.values))

    df["apartment_id"] = df.apply(lambda r: _id_row(r), axis=1)
    return df


def dedupe_latest_by_id(df: pd.DataFrame, time_col: str = "snapshot_time") -> pd.DataFrame:
    df = df.copy()
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    # keep the last snapshot per apartment_id
    if "apartment_id" in df.columns:
        df = df.sort_values(time_col)
        df = df.drop_duplicates(subset=["apartment_id"], keep="last").reset_index(drop=True)
    return df


def compute_price_per_m2_kab(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # ensure numeric inputs
    for c in ["rent_min", "rent_max", "area_min", "area_max"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # compute average fallback
    df["avg_rent"] = df[[c for c in ["rent_min", "rent_max"] if c in df.columns]].mean(axis=1)
    df["avg_area"] = df[[c for c in ["area_min", "area_max"] if c in df.columns]].mean(axis=1)

    # compute price per m2 as a range (min, max) using conservative bounds:
    # - cheapest possible: rent_min / area_max
    # - most expensive possible: rent_max / area_min
    def _safe_div(n, d):
        try:
            if pd.isna(n) or pd.isna(d):
                return np.nan
            d = float(d)
            if d == 0:
                return np.nan
            return float(n) / d
        except Exception:
            return np.nan

    df["price_per_m2_min"] = df.apply(lambda r: _safe_div(r.get("rent_min"), r.get("area_max")), axis=1)
    df["price_per_m2_max"] = df.apply(lambda r: _safe_div(r.get("rent_max"), r.get("area_min")), axis=1)

    # fallback to average-based estimate when range endpoints are missing
    avg_ppm = df["avg_rent"] / df["avg_area"]
    df.loc[df["price_per_m2_min"].isna(), "price_per_m2_min"] = avg_ppm[df["price_per_m2_min"].isna()]
    df.loc[df["price_per_m2_max"].isna(), "price_per_m2_max"] = avg_ppm[df["price_per_m2_max"].isna()]

    # round to 2 decimals for display
    df["price_per_m2_min"] = df["price_per_m2_min"].round(2)
    df["price_per_m2_max"] = df["price_per_m2_max"].round(2)

    def _fmt_range(a, b):
        try:
            if pd.notna(a) and pd.notna(b):
                # if min and max are effectively the same, show single value
                try:
                    a_f = float(a)
                    b_f = float(b)
                    # compare rounded values (2 decimals) so identical-looking
                    # ranges like 99.57 - 99.57 collapse to a single value
                    a_r = round(a_f, 2)
                    b_r = round(b_f, 2)
                    if abs(a_r - b_r) < 1e-8:
                        return f"{a_r:.2f}"
                    return f"{a_r:.2f} - {b_r:.2f}"
                except Exception:
                    return f"{float(a):.2f} - {float(b):.2f}"
            if pd.notna(a):
                return f"{float(a):.2f}"
            if pd.notna(b):
                return f"{float(b):.2f}"
        except Exception:
            pass
        return None

    df["price_per_m2_range"] = df.apply(lambda r: _fmt_range(r.get("price_per_m2_min"), r.get("price_per_m2_max")), axis=1)

    # numeric column used for sorting in price table: use the minimum possible price
    df["price_per_m2"] = df["price_per_m2_min"]
    df.loc[~np.isfinite(df["price_per_m2"]), "price_per_m2"] = np.nan
    # round the numeric estimate too
    if "price_per_m2" in df.columns:
        df["price_per_m2"] = df["price_per_m2"].round(2)
    return df


def compute_price_per_m2_sdk(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "estimated_price_kr" in df.columns:
        df["estimated_price_kr"] = pd.to_numeric(df["estimated_price_kr"], errors="coerce")
    if "area_m2" in df.columns:
        df["area_m2"] = pd.to_numeric(df["area_m2"], errors="coerce")
    df["price_per_m2"] = df["estimated_price_kr"] / df["area_m2"]
    df.loc[~np.isfinite(df["price_per_m2"]), "price_per_m2"] = np.nan
    # round for display consistency
    if "price_per_m2" in df.columns:
        df["price_per_m2"] = df["price_per_m2"].round(2)
    return df


def _prepare_kab_history(df_kab: pd.DataFrame) -> pd.DataFrame:
    df = df_kab.copy()
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors="coerce")
    if "place_in_queue" in df.columns:
        df["place_in_queue"] = pd.to_numeric(df["place_in_queue"], errors="coerce")
    # Keep only needed columns for the history plot
    cols = ["snapshot_time", "apartment_id", "place_in_queue", "addresses", "room_count", "company", "department", "tenancy_count"]
    existing = [c for c in cols if c in df.columns]
    return df[existing].sort_values(["apartment_id", "snapshot_time"]).reset_index(drop=True)


def _prepare_sdk_history(df_sdk: pd.DataFrame) -> pd.DataFrame:
    df = df_sdk.copy()
    if "snapshot_time" in df.columns:
        df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors="coerce")
    # prefer place_in_queue_min when available, else fallback to place_in_queue
    if "place_in_queue_min" in df.columns:
        df["place_in_queue_min"] = pd.to_numeric(df["place_in_queue_min"], errors="coerce")
    elif "place_in_queue" in df.columns:
        df["place_in_queue_min"] = pd.to_numeric(df["place_in_queue"], errors="coerce")
    cols = ["snapshot_time", "apartment_id", "place_in_queue_min", "building_name", "address"]
    existing = [c for c in cols if c in df.columns]
    # normalize column name to `place_in_queue` for plotting convenience
    res = df[existing].sort_values(["apartment_id", "snapshot_time"]).reset_index(drop=True)
    if "place_in_queue_min" in res.columns:
        res = res.rename(columns={"place_in_queue_min": "place_in_queue"})
    return res


def estimate_eta_to_zero(kab_full: pd.DataFrame, min_points: int = 2):
    """Estimate ETA to `place_in_queue <= 0` per apartment using a linear fit.

    Returns a DataFrame with columns: `apartment_id`, `last_snapshot`, `last_place`,
    `slope_per_day`, `days_to_zero`, `eta`.
    """
    rows = []
    if kab_full.empty:
        return pd.DataFrame()

    df = kab_full.copy()
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"], errors="coerce")
    if "place_in_queue" in df.columns:
        df["place_in_queue"] = pd.to_numeric(df["place_in_queue"], errors="coerce")

    for aid, g in df.groupby("apartment_id"):
        g = g.dropna(subset=["snapshot_time", "place_in_queue"]).sort_values("snapshot_time")
        if len(g) < min_points:
            continue
        # compute time in days relative to the first snapshot to improve numeric
        # conditioning for the linear fit (avoids very large absolute time values)
        try:
            t_days = (g["snapshot_time"] - g["snapshot_time"].iloc[0]).dt.total_seconds() / 86400.0
            t_days = t_days.values.astype(float)
        except Exception:
            # fallback: use integer seconds offset from min timestamp
            t = g["snapshot_time"].astype("int64") // 10 ** 9
            t_days = (t - t.min()) / (60 * 60 * 24)
            t_days = t_days.astype(float)

        y = g["place_in_queue"].values
        # require variance in y and in time (otherwise fit is meaningless)
        if np.nanstd(y) == 0 or np.nanstd(t_days) == 0:
            continue
        try:
            slope, intercept = np.polyfit(t_days, y, 1)
        except Exception:
            continue
        # we want slope < 0 (queue decreasing)
        if not np.isfinite(slope) or slope >= 0:
            continue
        last_snapshot = g["snapshot_time"].iloc[-1]
        last_y = y[-1]
        days_to_zero = float(last_y / (-slope))
        if days_to_zero < 0 or days_to_zero > 3650:
            # filter unrealistic results (>10 years)
            continue
        eta = pd.to_datetime(last_snapshot) + pd.Timedelta(days=days_to_zero)
        # capture some identifying metadata from the last row if available
        last_row = g.iloc[-1]
        rows.append(
            {
                "apartment_id": aid,
                "last_snapshot": pd.to_datetime(last_snapshot),
                "last_place": float(last_y),
                "slope_per_day": float(slope),
                "days_to_zero": days_to_zero,
                "eta": eta,
                "company": last_row.get("company") if "company" in last_row.index else None,
                "department": last_row.get("department") if "department" in last_row.index else None,
                "tenancy_count": last_row.get("tenancy_count") if "tenancy_count" in last_row.index else None,
            }
        )

    if not rows:
        return pd.DataFrame()
    res = pd.DataFrame(rows).sort_values("eta").reset_index(drop=True)
    return res


def load_and_prepare_all(data_dir: str = "data") -> Dict[str, pd.DataFrame]:
    """Load both sources and prepare the derived DataFrames used by the app.

    Returns a dict with keys:
      - `kab_latest`: newest-row-per-apartment for KAB
      - `sdk_latest`: newest-row-per-apartment for s.dk
      - `price_table`: combined price-per-m2 table (both sources)
      - `kab_history`: full KAB history series (for plotting)
      - `top10_eta`: top-10 ETA to queue=0 DataFrame
    """
    data = load_all_clean_data(data_dir)
    sdk = data.get("s_dk", pd.DataFrame())
    kab = data.get("kab", pd.DataFrame())

    # ensure snapshot_time exists and is datetime
    if "snapshot_time" in kab.columns:
        kab["snapshot_time"] = pd.to_datetime(kab["snapshot_time"], errors="coerce")
    if "snapshot_time" in sdk.columns:
        sdk["snapshot_time"] = pd.to_datetime(sdk["snapshot_time"], errors="coerce")

    # add deterministic ids
    kab = add_apartment_ids(kab, "kab")
    sdk = add_apartment_ids(sdk, "s_dk")

    # prepare history (full KAB) and keep an unfiltered copy
    kab_history_full = _prepare_kab_history(kab)
    kab_history = kab_history_full.copy()

    # Filter out apartments that never changed their place_in_queue (for default view)
    if kab_history_full is not None and not kab_history_full.empty:
        changing_aids = []
        for aid, g in kab_history_full.groupby("apartment_id"):
            if "place_in_queue" not in g.columns:
                continue
            vals = g["place_in_queue"].dropna().values
            if len(vals) >= 2 and np.nanstd(vals) != 0:
                changing_aids.append(aid)
        kab_history = kab_history_full[kab_history_full["apartment_id"].isin(changing_aids)].reset_index(drop=True)

    # compute 30-day change in place_in_queue per apartment (use the full history)
    place_change_map: Dict[str, float] = {}
    if kab_history_full is not None and not kab_history_full.empty:
        for aid, g in kab_history_full.groupby("apartment_id"):
            g = g.dropna(subset=["snapshot_time", "place_in_queue"]).sort_values("snapshot_time")
            if g.empty:
                # default to 0 when there's no prior data
                place_change_map[aid] = 0.0
                continue
            last_row = g.iloc[-1]
            cutoff = last_row["snapshot_time"] - pd.Timedelta(days=30)
            earlier = g[g["snapshot_time"] <= cutoff]
            if earlier.empty:
                # No snapshot older than 30 days — fall back to the earliest
                # available snapshot so we still report change over the
                # available period (which is <= 30 days).
                prev = g.iloc[0]
            else:
                prev = earlier.iloc[-1]

            if pd.notna(last_row["place_in_queue"]) and pd.notna(prev["place_in_queue"]):
                place_change_map[aid] = float(last_row["place_in_queue"] - prev["place_in_queue"])
            else:
                place_change_map[aid] = 0.0

    # newest per apartment
    kab_latest = dedupe_latest_by_id(kab, time_col="snapshot_time")
    sdk_latest = dedupe_latest_by_id(sdk, time_col="snapshot_time")

    # Normalize KAB building URLs: prepend base when URL appears relative
    kab_base = "https://www.kab-selvbetjening.dk"
    def _ensure_kab_url(u):
        if pd.isna(u) or u is None:
            return None
        s = str(u).strip()
        if not s:
            return None
        if s.startswith("http"):
            return s
        if s.startswith("/"):
            return kab_base + s
        return kab_base + "/" + s
    if not kab_latest.empty and "building_url" in kab_latest.columns:
        kab_latest = kab_latest.copy()
        kab_latest["building_url"] = kab_latest["building_url"].apply(_ensure_kab_url)

    # attach 30-day change to kab_latest (default 0)
    if not kab_latest.empty:
        kab_latest = kab_latest.copy()
        kab_latest["place_change_30d"] = kab_latest["apartment_id"].map(place_change_map).fillna(0.0)

    # Merge min/max rent and area into readable range columns for display
    if not kab_latest.empty:
        # ensure numeric types
        for col in ["rent_min", "rent_max", "area_min", "area_max"]:
            if col in kab_latest.columns:
                kab_latest[col] = pd.to_numeric(kab_latest[col], errors="coerce")

        def _fmt_money(rmin, rmax):
            if pd.notna(rmin) and pd.notna(rmax):
                try:
                    rmin_i = int(rmin) if float(rmin).is_integer() else int(round(rmin))
                    rmax_i = int(rmax) if float(rmax).is_integer() else int(round(rmax))
                except Exception:
                    rmin_i = rmin
                    rmax_i = rmax
                return f"{rmin_i} - {rmax_i} kr"
            if pd.notna(rmin):
                return f"{int(rmin)} kr"
            if pd.notna(rmax):
                return f"{int(rmax)} kr"
            return None

        def _fmt_area(amin, amax):
            if pd.notna(amin) and pd.notna(amax):
                try:
                    amin_i = int(amin) if float(amin).is_integer() else int(round(amin))
                    amax_i = int(amax) if float(amax).is_integer() else int(round(amax))
                except Exception:
                    amin_i = amin
                    amax_i = amax
                return f"{amin_i} - {amax_i} m2"
            if pd.notna(amin):
                return f"{int(amin)} m2"
            if pd.notna(amax):
                return f"{int(amax)} m2"
            return None

        kab_latest["rent_range"] = kab_latest.apply(lambda r: _fmt_money(r.get("rent_min"), r.get("rent_max")), axis=1)
        kab_latest["area_range"] = kab_latest.apply(lambda r: _fmt_area(r.get("area_min"), r.get("area_max")), axis=1)

        # compute price per m2 ranges (uses raw min/max columns); if computation fails, keep going
        try:
            kab_latest = compute_price_per_m2_kab(kab_latest)
        except Exception:
            pass

        # drop the raw min/max columns to keep the tables simple
        drop_cols = [c for c in ["rent_min", "rent_max", "area_min", "area_max"] if c in kab_latest.columns]
        if drop_cols:
            kab_latest = kab_latest.drop(columns=drop_cols)

    # prepare s.dk history series (use min queue value when available) and keep full copy
    sdk_history_full = _prepare_sdk_history(sdk)
    sdk_history = sdk_history_full.copy()
    # filter out s.dk apartments that never changed their place_in_queue
    if sdk_history_full is not None and not sdk_history_full.empty:
        changing_sdk_aids = []
        for aid, g in sdk_history_full.groupby("apartment_id"):
            if "place_in_queue" not in g.columns:
                continue
            vals = g["place_in_queue"].dropna().values
            if len(vals) >= 2 and np.nanstd(vals) != 0:
                changing_sdk_aids.append(aid)
        sdk_history = sdk_history_full[sdk_history_full["apartment_id"].isin(changing_sdk_aids)].reset_index(drop=True)

    # compute price per m2 for s.dk
    sdk_latest = compute_price_per_m2_sdk(sdk_latest)

    # combined price table
    price_rows = []
    # KAB rows
    for _, r in kab_latest.iterrows():
        price_rows.append(
            {
                "source": "kab",
                "apartment_id": r.get("apartment_id"),
                "label": r.get("addresses") if "addresses" in r else None,
                "url": r.get("building_url") if "building_url" in r else None,
                "area_m2": r.get("avg_area"),
                "price_estimate": r.get("avg_rent"),
                "price_per_m2": r.get("price_per_m2"),
                "place_in_queue": r.get("place_in_queue"),
            }
        )
    # s.dk rows
    for _, r in sdk_latest.iterrows():
        price_rows.append(
            {
                "source": "s_dk",
                "apartment_id": r.get("apartment_id"),
                "label": r.get("building_name") if "building_name" in r else r.get("address"),
                "url": r.get("url") if "url" in r else None,
                "area_m2": r.get("area_m2"),
                "price_estimate": r.get("estimated_price_kr"),
                "price_per_m2": r.get("price_per_m2"),
                "place_in_queue": r.get("place_in_queue"),
            }
        )

    price_table = pd.DataFrame(price_rows)
    if not price_table.empty:
        # round area_m2 for display
        if "area_m2" in price_table.columns:
            price_table["area_m2"] = pd.to_numeric(price_table["area_m2"], errors="coerce").round(2)
        price_table = price_table.sort_values("price_per_m2", na_position="last").reset_index(drop=True)

    # compute ETA top10 for KAB (use full history, not just latest)
    top10_eta = estimate_eta_to_zero(kab)

    # helper to format ETA as relative years/months/days
    now = pd.Timestamp.now()
    try:
        now_dt = datetime.fromtimestamp(now.timestamp())
    except Exception:
        now_dt = now.to_pydatetime()

    def _format_eta(eta_val):
        if pd.isna(eta_val):
            return None
        try:
            eta_ts = pd.to_datetime(eta_val)
        except Exception:
            return None
        try:
            eta_dt = datetime.fromtimestamp(eta_ts.timestamp())
        except Exception:
            try:
                eta_dt = eta_ts.to_pydatetime()
            except Exception:
                return None
        if eta_dt <= now_dt:
            return "<1 day"
        rd = relativedelta(eta_dt, now_dt)
        y, m, d = rd.years, rd.months, rd.days
        if y and y > 0:
            parts = [f"{y}y"]
            if m and m > 0:
                parts.append(f"{m}m")
            if d and d > 0:
                parts.append(f"{d}d")
            return " ".join(parts)
        if m and m > 0:
            parts = [f"{m}m"]
            if d and d > 0:
                parts.append(f"{d}d")
            return " ".join(parts)
        if d and d > 0:
            return f"{d}d"
        return "<1 day"

    # ensure we always have a DataFrame to work with
    if top10_eta is None or top10_eta.empty:
        top10_eta = pd.DataFrame(columns=["apartment_id", "last_snapshot", "last_place", "slope_per_day", "days_to_zero", "eta", "company", "department", "tenancy_count"])

    # add human-readable ETA-in string
    if "eta" in top10_eta.columns:
        top10_eta["eta_in"] = top10_eta["eta"].apply(_format_eta)
    else:
        top10_eta["eta_in"] = None

    # NOTE: we intentionally do NOT inject extra placeholder rows into
    # `top10_eta`. The Top-10 ETA table should show only apartments with
    # a computed ETA (i.e. a valid prediction). This avoids confusing rows
    # that lack an ETA but appear in the history plot.

    # merge place_change_30d and identification metadata from latest KAB data
    if not kab_latest.empty and "place_change_30d" in kab_latest.columns:
        meta = kab_latest[["apartment_id", "company", "department", "tenancy_count", "place_change_30d"]].copy()
        top10_eta = top10_eta.merge(meta, on="apartment_id", how="left")

    # normalize metadata columns so they are display-friendly (avoid all-NaN columns)
    if not top10_eta.empty:
        for c in ["company", "department"]:
            if c in top10_eta.columns:
                top10_eta[c] = top10_eta[c].fillna("")
        if "tenancy_count" in top10_eta.columns:
            # keep tenancy_count as numeric when present, else empty
            top10_eta["tenancy_count"] = top10_eta["tenancy_count"].where(pd.notna(top10_eta["tenancy_count"]), None)

    # add the requested change column name and reorder columns for display
    if "place_change_30d" in top10_eta.columns:
        top10_eta["changes_last_30_days"] = top10_eta["place_change_30d"]
    else:
        top10_eta["changes_last_30_days"] = None

    # ensure place_change_30d is numeric and filter out apartments that
    # did not change in the last 30 days — the Top-10 ETA should reflect
    # recent movement only (user expectation).
    if "place_change_30d" in top10_eta.columns:
        top10_eta["place_change_30d"] = pd.to_numeric(top10_eta["place_change_30d"], errors="coerce").fillna(0.0).astype(float)
        # keep only apartments with non-zero change in last 30 days
        top10_eta = top10_eta[top10_eta["place_change_30d"] != 0.0].reset_index(drop=True)

    # if some metadata columns are still empty, try to fill them from the
    # latest KAB snapshot as a fallback (ensure human-readable strings)
    if not top10_eta.empty and not kab_latest.empty:
        try:
            kab_meta_map = kab_latest.set_index("apartment_id")
            for c in ["company", "department"]:
                if c in kab_meta_map.columns:
                    top10_eta[c] = top10_eta[c].where(top10_eta[c].notna() & (top10_eta[c] != ""), top10_eta["apartment_id"].map(kab_meta_map[c]).fillna(""))
            if "tenancy_count" in kab_meta_map.columns:
                top10_eta["tenancy_count"] = top10_eta["tenancy_count"].where(pd.notna(top10_eta["tenancy_count"]), top10_eta["apartment_id"].map(kab_meta_map["tenancy_count"]))
        except Exception:
            pass

    # Normalize missing changes to 0.0 (user expectation); actual numeric
    # normalization and filtering is performed after slope override and
    # ETA recomputation below to ensure consistency.

    # Recompute days_to_zero, eta and human-readable eta_in using the
    # slope values computed by `estimate_eta_to_zero`. Do NOT override
    # the slope based on the 30-day change; keep the fitted slope so the
    # Top-10 reflects the fitted trends from the full history.
    if not top10_eta.empty:
        days_list = []
        eta_list = []
        for _, r in top10_eta.iterrows():
            slope = r.get("slope_per_day")
            last_place = r.get("last_place")
            last_snapshot = r.get("last_snapshot")
            try:
                # require a valid, negative slope and valid last snapshot/place
                if pd.isna(slope) or not np.isfinite(slope) or float(slope) >= 0 or pd.isna(last_place) or pd.isna(last_snapshot):
                    days_list.append(None)
                    eta_list.append(None)
                    continue
            except Exception:
                days_list.append(None)
                eta_list.append(None)
                continue
            try:
                days_to_zero = float(last_place) / (-float(slope))
                if days_to_zero < 0 or days_to_zero > 3650:
                    days_list.append(None)
                    eta_list.append(None)
                    continue
                days_list.append(days_to_zero)
                eta_val = pd.to_datetime(last_snapshot) + pd.Timedelta(days=days_to_zero)
                eta_list.append(eta_val)
            except Exception:
                days_list.append(None)
                eta_list.append(None)
        top10_eta["days_to_zero"] = days_list
        top10_eta["eta"] = eta_list
        # update human-readable string
        if "eta" in top10_eta.columns:
            top10_eta["eta_in"] = top10_eta["eta"].apply(_format_eta)
        else:
            top10_eta["eta_in"] = None
        # sort by ETA (unknowns last)
        try:
            top10_eta = top10_eta.sort_values("eta", na_position="last").reset_index(drop=True)
        except Exception:
            top10_eta = top10_eta.reset_index(drop=True)

    # Filter out entries without a valid ETA. Keep ETA rows regardless of
    # their 30-day change value so the Top-10 reflects fitted trends from
    # the full history (but still show the 30-day change as a column).
    if not top10_eta.empty:
        # ensure numeric column exists and is numeric for display only
        if "changes_last_30_days" not in top10_eta.columns:
            top10_eta["changes_last_30_days"] = 0.0
        else:
            top10_eta["changes_last_30_days"] = pd.to_numeric(top10_eta["changes_last_30_days"], errors="coerce").fillna(0.0).astype(float)

        # keep only apartments with a computed ETA
        if "eta" in top10_eta.columns:
            top10_eta = top10_eta[top10_eta["eta"].notna()].reset_index(drop=True)
        else:
            top10_eta = top10_eta.reset_index(drop=True)

    # ensure columns exist and pick order: company, department, tenancy_count, last_place, eta_in, slope_per_day, changes_last_30_days
    for col in ["company", "department", "tenancy_count", "last_place", "eta_in", "slope_per_day", "changes_last_30_days"]:
        if col not in top10_eta.columns:
            top10_eta[col] = None

    top10_eta = top10_eta[["company", "department", "tenancy_count", "last_place", "eta_in", "slope_per_day", "changes_last_30_days", "apartment_id"]]
    top10_eta = top10_eta.reset_index(drop=True)

    # Summary stats (simple) for dashboard
    def _stats_for(df: pd.DataFrame, name: str) -> Dict[str, Any]:
        if df is None or df.empty:
            return {
                "dataset": name,
                "n_listings": 0,
                "nearest_eta": None,
                "lowest_place_in_queue": None,
                "newest_snapshot": None,
            }
        # newest snapshot for this dataset
        newest_snapshot = None
        if "snapshot_time" in df.columns and df["snapshot_time"].notna().any():
            try:
                newest_snapshot = pd.to_datetime(df["snapshot_time"]).max()
                newest_snapshot = newest_snapshot.isoformat()
            except Exception:
                newest_snapshot = None

        # compute lowest place in queue (for s_dk prefer interval if available)
        lowest_place = None
        if name == "s_dk":
            # Choose the interval corresponding to the smallest `place_in_queue_min`.
            pmin = None
            pmax = None
            if "place_in_queue_min" in df.columns and df["place_in_queue_min"].notna().any():
                try:
                    # find the row with the minimal place_in_queue_min and take its paired max
                    pmin_col = pd.to_numeric(df["place_in_queue_min"], errors="coerce")
                    idx = pmin_col.idxmin()
                    if pd.notna(idx):
                        candidate_min = pmin_col.loc[idx]
                        if pd.notna(candidate_min):
                            pmin = int(candidate_min)
                            if "place_in_queue_max" in df.columns:
                                try:
                                    pmax_val = pd.to_numeric(df.at[idx, "place_in_queue_max"], errors="coerce")
                                    if pd.notna(pmax_val):
                                        pmax = int(pmax_val)
                                except Exception:
                                    pmax = None
                except Exception:
                    pmin = None
                    pmax = None
            if pmin is not None and pmax is not None:
                lowest_place = f"{pmin} - {pmax}"
            elif pmin is not None:
                lowest_place = str(pmin)
            else:
                # fallback to single place_in_queue value
                if "place_in_queue" in df.columns and df["place_in_queue"].notna().any():
                    try:
                        lowest_place = int(pd.to_numeric(df["place_in_queue"], errors="coerce").min())
                    except Exception:
                        lowest_place = None
        else:
            if "place_in_queue" in df.columns and df["place_in_queue"].notna().any():
                try:
                    lowest_place = float(pd.to_numeric(df["place_in_queue"], errors="coerce").min())
                except Exception:
                    lowest_place = None

        # For KAB, rows may represent grouped apartments. Use the
        # `tenancy_count` column (when available) to compute the actual
        # apartment count. Fall back to row-count when tenancy_count is
        # missing or cannot be parsed.
        n_listings_value = None
        if name == "kab" and "tenancy_count" in df.columns:
            try:
                tc = pd.to_numeric(df["tenancy_count"], errors="coerce")
                # Treat missing tenancy_count as a single apartment
                tc = tc.fillna(1)
                n_listings_value = int(tc.sum())
            except Exception:
                n_listings_value = int(len(df))
        else:
            n_listings_value = int(len(df))

        return {
            "dataset": name,
            "n_listings": n_listings_value,
            "nearest_eta": None,
            "lowest_place_in_queue": lowest_place,
            "newest_snapshot": newest_snapshot,
        }

    # add nearest ETA info and compute combined lowest place
    # Summary for KAB and s.dk only (omit combined price table row)
    summary_stats = pd.DataFrame([
        _stats_for(kab_latest, "kab"),
        _stats_for(sdk_latest, "s_dk"),
    ])

    # nearest ETA (from top10_eta) - use human-readable `eta_in` if available
    nearest_eta_str = None
    if top10_eta is not None and not top10_eta.empty and "eta_in" in top10_eta.columns:
        try:
            # top10_eta is sorted by ETA; take the first human-readable string
            nearest_eta_str = top10_eta["eta_in"].iloc[0]
        except Exception:
            nearest_eta_str = None

    # attach nearest ETA only to the KAB summary row
    if not summary_stats.empty:
        for idx, row in summary_stats.iterrows():
            if row["dataset"] == "kab":
                summary_stats.at[idx, "nearest_eta"] = nearest_eta_str

    # (no combined summary row; overall lowest is not attached here)

    # enrich the history frames with latest metadata so hover/context shows company/department
    try:
        if kab_history_full is not None and not kab_history_full.empty and not kab_latest.empty:
            # prefer a stable small meta frame with the columns we want to inject
            meta_cols = [c for c in ["apartment_id", "company", "department", "tenancy_count"] if c in kab_latest.columns]
            if meta_cols:
                meta_df = kab_latest[meta_cols].copy()

                # merge into the full history using suffixes and then coalesce so
                # we keep any original history values and fill missing ones from latest
                kab_history_full = kab_history_full.merge(meta_df, on="apartment_id", how="left", suffixes=("", "_meta"))
                for c in ["company", "department", "tenancy_count"]:
                    meta_name = f"{c}_meta"
                    if meta_name in kab_history_full.columns:
                        try:
                            # prefer existing history value where present; otherwise
                            # take the value from the latest snapshot (meta column)
                            def _coalesce(row, col=c, mcol=meta_name):
                                val = row.get(col)
                                if val is None or (isinstance(val, float) and np.isnan(val)) or (isinstance(val, str) and str(val).strip() == ""):
                                    return row.get(mcol)
                                return val
                            kab_history_full[c] = kab_history_full.apply(_coalesce, axis=1)
                            kab_history_full = kab_history_full.drop(columns=[meta_name])
                        except Exception:
                            pass

                # also merge into the filtered history view so the plot hover shows metadata
                if kab_history is not None and not kab_history.empty:
                    kab_history = kab_history.merge(meta_df, on="apartment_id", how="left", suffixes=("", "_meta"))
                    for c in ["company", "department", "tenancy_count"]:
                        meta_name = f"{c}_meta"
                        if meta_name in kab_history.columns:
                            try:
                                def _coalesce_h(row, col=c, mcol=meta_name):
                                    val = row.get(col)
                                    if val is None or (isinstance(val, float) and np.isnan(val)) or (isinstance(val, str) and str(val).strip() == ""):
                                        return row.get(mcol)
                                    return val
                                kab_history[c] = kab_history.apply(_coalesce_h, axis=1)
                                kab_history = kab_history.drop(columns=[meta_name])
                            except Exception:
                                pass
    except Exception:
        pass

    # Keep the filtered `kab_history` intact regardless of whether we have
    # computed ETAs. The full history (`kab_history_full`) remains available
    # when the user toggles "Show all data" in the UI.

    return {
        "kab_latest": kab_latest,
        "sdk_latest": sdk_latest,
        "price_table": price_table,
        "kab_history": kab_history,
        "kab_history_full": kab_history_full,
        "sdk_history": sdk_history,
        "sdk_history_full": sdk_history_full,
        "top10_eta": top10_eta,
        "summary_stats": summary_stats,
    }


__all__ = [
    "load_and_prepare_all",
    "add_apartment_ids",
    "dedupe_latest_by_id",
    "compute_price_per_m2_kab",
    "compute_price_per_m2_sdk",
    "estimate_eta_to_zero",
]
