WITH item_totals AS (
  SELECT order_id, SUM(price) + SUM(freight_value) AS expected_total
  FROM stg_items GROUP BY order_id
), payment_totals AS (
  SELECT order_id, SUM(payment_value) AS paid_total
  FROM stg_payments GROUP BY order_id
)
SELECT COUNT(*) AS mismatched_orders
FROM item_totals i
JOIN payment_totals p USING (order_id)
WHERE ABS(i.expected_total - p.paid_total) > 1.00;
