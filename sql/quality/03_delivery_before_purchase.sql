SELECT COUNT(*) AS failing_rows
FROM stg_orders
WHERE order_delivered_customer_date IS NOT NULL
  AND order_purchase_timestamp IS NOT NULL
  AND julianday(order_delivered_customer_date) < julianday(order_purchase_timestamp);
