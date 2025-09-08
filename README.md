# Sparrow-Song

# VENV commands
## macOS / Linux
```
source .venv/bin/activate
python -V
pip list
deactivate
```

## Update VENV
```
deactivate || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## yfinance API
https://ranaroussi.github.io/yfinance/

## Querying yfinance
1. Update tickers in settings.yaml
2. Update calender type in settings.yaml (optional)
3. Run ```Make data```

### View Parquet files using SQL
1. Creat SQL command in /sql
2. run ```duckdb < sql/file.sql```

# Phase 1 — Project Bootstrap
## What’s installed & why

### Core / Numerics:

pandas — tabular ops; read/write Parquet.

numpy — vectorized math used by pandas & models.

scipy, statsmodels — (later) stats/tests/regressions.

### Data & Viz:

yfinance — market data (OHLCV + Adj Close).

matplotlib, plotly — (later) plotting/reporting.

### Backtesting / Research (later):

vectorbt — fast vectorized research & backtests.

backtrader — event-driven backtester/live engine.

alphalens-reloaded — factor IC/IR, quantile tearsheets.

### ML / Modeling (later):

scikit-learn — splits, pipelines, classic ML.

xgboost, lightgbm — gradient boosting.

umap-learn — dimensionality reduction.

optuna — hyperparameter tuning.

shap — model explainability.

### Portfolio / Risk (later):

PyPortfolioOpt — sizing/optimization (MV, HRP, BL).

### Indicators (later):

ta — pure-Python technical indicators.

(Optional: TA-Lib if we want the C lib later.)

### Storage:

pyarrow — Parquet IO engine.

Calendars (optional) exchange-calendars — venue trading sessions/holidays.

### Dev Tooling:
pre-commit — runs checks on git commit.

ruff — linter + fixer (and formatter if you prefer).

black — formatter (enable if on Py ≥ 3.12.6 or 3.11).

nbqa — run linters/formatters on notebooks.

ipykernel — register this venv as a Jupyter kernel.

DuckDB is used from the shell (e.g., Homebrew) to query Parquet; it’s not in requirements.txt.

### Makefile targets (quality-of-life)
make install — create venv + install requirements.

make hooks — install pre-commit hooks.

make lint — ruff check .

make format — ruff --fix (and black if enabled).

make nbformat — run tools on notebooks via nbqa.

### Notes
Venv lives at ./.venv. Make targets call tools via .venv/bin/..., so manual activation isn’t required.

If you keep Black: avoid Python 3.12.5 (known issue); use 3.12.6+ or 3.11.

# Phase 2 — Ingestion & Cleaning
## Config
config/settings.yaml

source: yfinance

tickers: [SPY, AAPL, MSFT]

```
start: "2015-01-01"
end: ""               # empty = up to latest
interval: "1d"
```

### Calendar policy:
-  "B"     = BusinessDay (default)
- "XNYS"  = exchange sessions via exchange-calendars
- "AUTO"  = union of observed dates across tickers

calendar: "B"

ffill_limit: 5

paths:
  raw: "data/raw/yfinance"
  processed: "data/processed"

# Columns kept in processed parquet
columns: [open, high, low, close, adj_close, volume, ret_1d]

### Data flow (pipeline steps)

1. Download OHLCV (+ Adj Close) via yfinance.
2. Normalize columns to lowercase; enforce dtypes.
3.Adjust OHLCV using factor adj_close/close (handles splits; scale volume inversely).
4. Align calendar to a common index:
    - calendar: "B" → business days
    - "XNYS" → exchange sessions via exchange-calendars
    - "AUTO" → union of observed dates
    - Forward-fill up to ffill_limit small gaps.
5. Add features: ret_1d (adj-close pct change).
6. Persist to Parquet (pyarrow, compressed)
    - Raw per ticker → data/raw/yfinance/<TICKER>.parquet
    - Long table → data/processed/prices_daily.parquet (MultiIndex: date, ticker)
    - Wide table → data/processed/prices_daily_wide.parquet (flattened columns like close_AAPL, volume_MSFT)
7. Manifest (optional) → data/processed/_manifest.json
    - Min/max date & row counts per ticker for quick coverage checks.

### Incremental updates
- Re-runs fetch only from the last saved date + 1 if a raw Parquet exists (append, then rewrite).
- Use when you want new bars without refetching history.

### Validation
- scripts/validate_data.py runs structural/sanity checks:
    - duplicate indices, monotonic dates per ticker, NA thresholds, non-negative volumes, reasonable price ranges.

### Makefile targets
- make data / make update — run ingestion (fetch new data if available, then rebuild processed).
- make validate — run data QA on processed Parquet.
- make rebuild — don’t refetch; recompute processed from raw (use after changing processing logic).
- make refresh — wipe raw & processed, full re-download and rebuild.
- make peek — quick head/info of raw & processed files (optional helper).
- make sql FILE=sql/your_query.sql — run a DuckDB SQL script against Parquet.

### Querying Parquet with DuckDB
Place queries in sql/*.sql, then:
- duckdb < sql/last_10_aapl.sql

### or
- make sql FILE=sql/last_10_aapl.sql

- Example (long table):
```
SELECT date, ticker, close, volume
FROM 'data/processed/prices_daily.parquet'
WHERE ticker='AAPL'
ORDER BY date DESC
LIMIT 10;
Example (wide table; flattened names):
SELECT date, "close_AAPL" AS close_aapl, "volume_MSFT" AS vol_msft
FROM 'data/processed/prices_daily_wide.parquet'
ORDER BY date DESC
LIMIT 5;
```

### Folder layout (so far)
```
.
├─ Makefile
├─ requirements.txt
├─ .pre-commit-config.yaml
├─ pyproject.toml
├─ config/
│  └─ settings.yaml
├─ src/
│  └─ data/
│     ├─ ingest.py
│     └─ __init__.py
├─ scripts/
│  ├─ download_data.py
│  └─ validate_data.py
├─ data/
│  ├─ raw/
│  │  └─ yfinance/   # <TICKER>.parquet
│  └─ processed/
│     ├─ prices_daily.parquet
│     ├─ prices_daily_wide.parquet
│     └─ _manifest.json
└─ sql/
   └─ last_10_aapl.sql

```
