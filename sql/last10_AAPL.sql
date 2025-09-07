-- Show the latest 10 AAPL rows from the processed (long) table
SELECT date, ticker, close, volume
FROM 'data/processed/prices_daily.parquet'
WHERE ticker = 'AAPL'
ORDER BY date DESC
LIMIT 10;
