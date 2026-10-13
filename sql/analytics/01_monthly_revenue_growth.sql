WITH monthly AS (
  SELECT strftime('%Y-%m', order_purchase_timestamp) AS month,
         SUM(item_revenue) AS revenue
  FROM mart_order_summary
  WHERE order_status NOT IN ('canceled', 'unavailable')
  GROUP BY strftime('%Y-%m', order_purchase_timestamp)
), comparison AS (
  SELECT month, revenue,
         LAG(revenue) OVER (ORDER BY month) AS previous_month_revenue
  FROM monthly
)
SELECT month, revenue, previous_month_revenue,
       CASE WHEN previous_month_revenue IS NULL OR previous_month_revenue = 0 THEN NULL
            ELSE 100.0 * (revenue - previous_month_revenue) / previous_month_revenue END AS growth_pct
FROM comparison
ORDER BY month;
