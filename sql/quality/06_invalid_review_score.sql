SELECT COUNT(*) AS failing_rows
FROM stg_reviews
WHERE review_score IS NOT NULL AND review_score NOT BETWEEN 1 AND 5;
