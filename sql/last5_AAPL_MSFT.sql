SELECT date, "close_AAPL", "volume_MSFT"
FROM 'data/processed/prices_daily_wide.parquet'
ORDER BY date DESC
LIMIT 5;
