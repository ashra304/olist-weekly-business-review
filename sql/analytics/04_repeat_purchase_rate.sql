WITH customer_orders AS (
  SELECT customer_unique_id, COUNT(DISTINCT order_id) AS order_count
  FROM mart_order_summary
  WHERE customer_unique_id IS NOT NULL
  GROUP BY customer_unique_id
)
SELECT 100.0 * SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END)
             / NULLIF(COUNT(*), 0) AS repeat_customer_rate_pct,
       SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
       COUNT(*) AS distinct_customers
FROM customer_orders;
