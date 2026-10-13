WITH category_revenue AS (
  SELECT c.customer_state, p.product_category_name,
         SUM(oi.price) AS revenue
  FROM stg_orders o
  JOIN stg_customers c ON o.customer_id = c.customer_id
  JOIN stg_items oi ON o.order_id = oi.order_id
  JOIN stg_products p ON oi.product_id = p.product_id
  WHERE o.order_status NOT IN ('canceled', 'unavailable')
  GROUP BY c.customer_state, p.product_category_name
), ranked AS (
  SELECT *, DENSE_RANK() OVER (
    PARTITION BY customer_state ORDER BY revenue DESC
  ) AS category_rank
  FROM category_revenue
)
SELECT customer_state, product_category_name, revenue, category_rank
FROM ranked
WHERE category_rank <= 3
ORDER BY customer_state, category_rank, product_category_name;
