import sys
import pandas as pd

P = "data/processed/prices_daily.parquet"


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main():
    df = pd.read_parquet(P)

    # 1) structure
    if list(df.index.names) != ["date", "ticker"]:
        fail(f"Index should be ['date','ticker'], got {df.index.names}")

    # 2) duplicates
    if not df.index.is_unique:
        fail("Duplicate (date,ticker) rows found")

    # 3) monotonic dates per ticker
    by_tkr = df.reset_index().groupby("ticker")["date"]
    if not by_tkr.apply(lambda s: s.is_monotonic_increasing).all():
        fail("Dates not monotonic within at least one ticker")

    # 4) nulls (tolerate early leading NaNs)
    critical = ["open", "high", "low", "close", "adj_close", "volume"]
    for c in [x for x in critical if x in df.columns]:
        share = df[c].isna().mean()
        if share > 0.02:
            fail(f"Too many NaNs in {c}: {share:.2%}")

    # 5) value ranges
    if "close" in df and (df["close"] <= 0).any():
        fail("Non-positive prices found")
    if "volume" in df and (df["volume"] < 0).any():
        fail("Negative volumes found")

    d0, d1 = (
        df.index.get_level_values("date").min(),
        df.index.get_level_values("date").max(),
    )
    print(f"[OK] {P} looks sane. Range: {d0.date()} → {d1.date()}, rows={len(df):,}")


if __name__ == "__main__":
    main()
