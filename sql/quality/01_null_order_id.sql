SELECT COUNT(*) AS failing_rows
FROM stg_orders
WHERE order_id IS NULL OR TRIM(order_id) = '';
