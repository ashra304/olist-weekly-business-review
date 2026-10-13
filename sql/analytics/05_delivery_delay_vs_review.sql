SELECT CAST(ROUND(delivery_delay_days) AS INTEGER) AS delay_days_vs_estimate,
       COUNT(*) AS delivered_orders,
       ROUND(AVG(review_score), 2) AS avg_review_score
FROM mart_order_summary
WHERE delivery_delay_days IS NOT NULL AND review_score IS NOT NULL
GROUP BY CAST(ROUND(delivery_delay_days) AS INTEGER)
ORDER BY delay_days_vs_estimate;
