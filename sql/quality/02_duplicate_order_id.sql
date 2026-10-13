SELECT COUNT(*) AS duplicate_order_groups
FROM (
  SELECT order_id
  FROM stg_orders
  GROUP BY order_id
  HAVING COUNT(*) > 1
);
