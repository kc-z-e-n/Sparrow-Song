import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yfinance as yf
import yaml


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg


def _fetch_yf(ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
    """Download OHLCV (+ Adj Close) from yfinance and normalize columns."""
    df = yf.download(
        tickers=ticker,
        start=start or None,
        end=end or None,
        interval=interval,
        auto_adjust=False,  # keep raw; we'll compute adjusted OHLC
        progress=False,
        threads=True,
        group_by="column",  # fields as top-level, tickers as second-level (if any)
    )
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    # --- FLATTEN COLUMNS IF THEY ARE MULTIINDEX ---
    if isinstance(df.columns, pd.MultiIndex):
        # Typical yfinance shape: level 0 = field, level 1 = ticker
        # If only one ticker, drop that level entirely.
        if df.columns.nlevels == 2:
            # Option 1: if the second level has only one unique value, drop it:
            if len(df.columns.get_level_values(1).unique()) == 1:
                df.columns = df.columns.droplevel(1)
            else:
                # Option 2: pick the slice for our ticker explicitly
                df = df.xs(ticker, axis=1, level=1)
        else:
            # Fallback: join levels into single strings
            df.columns = ["_".join(map(str, lev)) for lev in df.columns]

    # Now we should have single-level columns like 'Open', 'High', ...
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    # Normalize index/column dtypes
    df.index = pd.to_datetime(df.index).tz_localize(None)

    # Coerce numeric types safely
    for c in ["open", "high", "low", "close", "adj_close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = (
            pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
        )

    return df


def _adjust_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build adjusted OHLC using the adj_factor = adj_close / close.
    Adjust volume by 1/adj_factor (for split effects).
    """
    if "adj_close" not in df or "close" not in df:
        return df.copy()

    adj_factor = (df["adj_close"] / df["close"]).replace([pd.NA, pd.NaT], pd.NA)
    adj_factor = adj_factor.fillna(1.0)

    out = df.copy()
    for c in ["open", "high", "low", "close"]:
        out[c] = (out[c] * adj_factor).astype("float64")
    # volume roughly scales inversely with split factor
    out["volume"] = (out["volume"] / adj_factor).round().astype("int64")

    return out


def _build_calendar(
    dfs: Dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
    freq: str,
) -> pd.DatetimeIndex:
    """Return a DatetimeIndex to reindex against, based on the chosen policy."""
    f = str(freq).upper()

    # AUTO: use the union of dates we actually have (good for mixed markets)
    if f == "AUTO":
        idx = sorted(set().union(*(df.index for df in dfs.values())))
        return pd.DatetimeIndex(idx)

    # Simple pandas calendars
    if f in {"B", "C", "D", "W", "M", "BM"}:
        return pd.date_range(start=start, end=end, freq=f)

    # Exchange calendars (e.g., "XNYS", "XNAS", "XTKS", "XLON")
    try:
        import exchange_calendars as xcals
    except ImportError as e:
        raise RuntimeError(
            f"Calendar '{freq}' requires the 'exchange-calendars' package. "
            f"Add it to requirements.txt and run make install."
        ) from e

    cal = xcals.get_calendar(f)
    sessions = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    # Make index naive (your price data is naive)
    if getattr(sessions, "tz", None) is not None:
        sessions = sessions.tz_localize(None)
    return pd.DatetimeIndex(sessions)


def _align_calendar(
    dfs: Dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
    freq: str = "B",
    ffill_limit: int = 5,
) -> Dict[str, pd.DataFrame]:
    """
    Reindex each ticker to a common calendar, forward-fill small gaps,
    and drop leading rows that are still NaN.
    """
    calendar = _build_calendar(dfs, start, end, freq)
    aligned: Dict[str, pd.DataFrame] = {}

    for tkr, df in dfs.items():
        r = df.reindex(calendar)
        r = r.ffill(limit=int(ffill_limit))

        first_valid = r["close"].first_valid_index()
        if first_valid is not None:
            r = r.loc[first_valid:]
        aligned[tkr] = r

    return aligned


def _add_returns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ret_1d"] = out["adj_close"].pct_change()
    return out


def _save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")


def ingest_from_config(config_path: str) -> None:
    cfg = load_config(config_path)

    tickers: List[str] = cfg["tickers"]
    start = cfg.get("start") or None
    end = cfg.get("end") or None
    interval = cfg.get("interval", "1d")
    cal = cfg.get("calendar", "B")
    ffill_limit = int(cfg.get("ffill_limit", 5))

    raw_dir = Path(cfg["paths"]["raw"])
    processed_dir = Path(cfg["paths"]["processed"])
    cols_keep = [c.lower() for c in cfg.get("columns", [])] or None

    # 1) Fetch each ticker
    raw_dfs: Dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = _fetch_yf(t, start, end, interval)
        _save_parquet(df, raw_dir / f"{t}.parquet")
        raw_dfs[t] = df

    # 2) Adjust OHLCV using adj_close
    adj_dfs = {t: _adjust_ohlcv(df) for t, df in raw_dfs.items()}

    # 3) Align calendars (union range)
    global_start = min(df.index.min() for df in adj_dfs.values())
    global_end = max(df.index.max() for df in adj_dfs.values())
    aligned = _align_calendar(
        adj_dfs, global_start, global_end, freq=cal, ffill_limit=ffill_limit
    )

    # 4) Add returns, choose columns, and stack to MultiIndex (date, ticker)
    post = {}
    for t, df in aligned.items():
        df = _add_returns(df)
        if cols_keep:
            df = df[[c for c in cols_keep if c in df.columns]]
        # add a level for ticker
        df["ticker"] = t
        post[t] = (
            df.reset_index()
            .rename(columns={"index": "date"})
            .set_index(["date", "ticker"])
        )

    combined = pd.concat(post.values(), axis=0).sort_index()

    # 5) Persist processed
    _save_parquet(combined, processed_dir / "prices_daily.parquet")

    # 6) Also save a wide table (columns per (field, ticker)) for convenience
    wide = combined.unstack(level="ticker")
    wide.columns = pd.Index(
        [f"{lvl0}_{lvl1}" for (lvl0, lvl1) in wide.columns.to_flat_index()]
    )
    _save_parquet(wide, processed_dir / "prices_daily_wide.parquet")

    print(f"[OK] Saved raw → {raw_dir}, processed → {processed_dir}")

    meta = []
    for t, df in aligned.items():
        if df.empty:
            continue
        meta.append(
            {
                "ticker": t,
                "min_date": str(df.index.min().date()),
                "max_date": str(df.index.max().date()),
                "rows": int(len(df)),
            }
        )
    pd.DataFrame(meta).to_json(
        processed_dir / "_manifest.json", orient="records", indent=2
    )


def main():
    parser = argparse.ArgumentParser(
        description="Ingest OHLCV and build processed parquet files."
    )
    parser.add_argument(
        "--config", default="config/settings.yaml", help="Path to YAML config."
    )
    args = parser.parse_args()
    ingest_from_config(args.config)


if __name__ == "__main__":
    main()
