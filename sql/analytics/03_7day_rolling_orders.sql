WITH daily AS (
  SELECT date(order_purchase_timestamp) AS order_date,
         COUNT(DISTINCT order_id) AS order_count
  FROM mart_order_summary
  GROUP BY date(order_purchase_timestamp)
), rolling AS (
  SELECT order_date, order_count,
         AVG(order_count) OVER (
           ORDER BY julianday(order_date)
           RANGE BETWEEN 6 PRECEDING AND CURRENT ROW
         ) AS rolling_7_day_avg
  FROM daily
)
SELECT order_date, order_count, rolling_7_day_avg
FROM rolling
ORDER BY order_date;
