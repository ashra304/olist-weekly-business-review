-- Generate a continuous calendar between the min and max order dates,
-- fill days with zero orders, and compute a 7-day rolling average
-- (current day + preceding 6 calendar days).

WITH bounds AS (
  SELECT DATE(MIN(order_purchase_timestamp)) AS min_date,
         DATE(MAX(order_purchase_timestamp)) AS max_date
  FROM mart_order_summary
),
-- Recursive calendar from min_date to max_date (inclusive)
calendar(order_date) AS (
  SELECT min_date FROM bounds
  UNION ALL
  SELECT DATE(julianday(order_date) + 1)
  FROM calendar, bounds
  WHERE order_date < bounds.max_date
),
-- base daily counts from the mart (may omit dates with zero orders)
base_daily AS (
  SELECT DATE(order_purchase_timestamp) AS order_date,
         COUNT(DISTINCT order_id) AS order_count
  FROM mart_order_summary
  GROUP BY DATE(order_purchase_timestamp)
),
-- left join calendar to base_daily to ensure every calendar date is present
daily AS (
  SELECT c.order_date,
         COALESCE(b.order_count, 0) AS order_count
  FROM calendar c
  LEFT JOIN base_daily b USING(order_date)
),
-- rolling average over the current date and previous 6 calendar days
rolling AS (
  SELECT d1.order_date,
         d1.order_count,
         -- correlated subquery to be fully SQLite-compatible
         (SELECT AVG(d2.order_count)
          FROM daily d2
          WHERE julianday(d2.order_date) BETWEEN julianday(d1.order_date) - 6
                                               AND julianday(d1.order_date)
         ) AS rolling_7_day_avg
  FROM daily d1
)
SELECT order_date,
       order_count,
       ROUND(rolling_7_day_avg, 2) AS rolling_7_day_avg
FROM rolling
ORDER BY order_date;
