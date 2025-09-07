# Sparrow-Song

# VENV commands
## macOS / Linux
source .venv/bin/activate
python -V
pip list
deactivate

## Update VENV
deactivate || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

## yfinance API
https://ranaroussi.github.io/yfinance/

## Querying yfinance
1. Update tickers in settings.yaml
2. Update calender type in settings.yaml (optional)
3. Run ```Make data```

### View Parquet files using SQL
1. Creat SQL command in /sql
2. run ```duckdb < sql/file.sql```
