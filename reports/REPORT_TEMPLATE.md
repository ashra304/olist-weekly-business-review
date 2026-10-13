# Weekly Business Review — Olist E-commerce

**Author:** [Your name]  
**Run date:** [date]  
**Dataset:** Olist Brazilian E-Commerce Public Dataset (2016–2018)

## 1. Pipeline and data quality
The ELT pipeline loads seven source CSVs into raw tables, creates typed staging tables, and builds `mart_order_summary` at one row per order. Raw, staging, and mart tables are replaced on each run, making reruns idempotent. Missing files/columns raise explicit errors; pipeline steps and quality checks are logged.

Paste actual output from `python pipeline.py` here:

| Check | Failing rows/groups | Treatment and rationale |
|---|---:|---|
| Null order ID | [actual] | Stop pipeline; an order without a key cannot be reliably joined. |
| Duplicate order ID | [actual] | Stop pipeline; investigate duplicates before aggregation. |
| Delivery before purchase | [actual] | Flag; do not silently alter source timestamps. |
| Order without customer | [actual] | Flag and investigate referential integrity. |
| Payment vs item + freight differs by > R$1 | [actual] | Flag; rounding/installments or source issues may explain differences. |
| Invalid review score | [actual] | Stop and investigate values outside 1–5. |

## 2. SQL analysis
Run the five queries in `sql/analytics/` and paste the key output/summary:
1. Monthly merchandise revenue and month-over-month growth.
2. Top three product categories by customer state.
3. Seven-day rolling average of daily orders.
4. Repeat-purchase rate using `customer_unique_id` to identify a person across orders.
5. Delivery delay relative to estimated date and average review score.

## 3. Metrics
**North Star — Successfully fulfilled order rate**  
Formula: delivered orders / all orders × 100.  
Why: balances demand with the ability to complete customer orders successfully.

**Supporting / guardrail metrics**
- **Merchandise revenue:** sum of item `price` for non-canceled/non-unavailable orders; measures sales excluding shipping.
- **On-time delivery rate:** delivered orders with actual delivery timestamp ≤ estimated delivery timestamp / delivered orders with both dates × 100; tracks fulfilment reliability.
- **Average review score:** mean of available review scores; customer experience guardrail.
- **Repeat-customer rate:** distinct `customer_unique_id` with ≥2 orders / all distinct `customer_unique_id` × 100; indicates retention.

## 4. Charts
Insert the four generated charts from `reports/generated/`:
- Monthly merchandise revenue
- Review-score distribution
- Average review score by delivery delay
- Top 10 customer states by merchandise revenue

## 5. One-page memo to the VP
**Subject: Prioritising delivery reliability to improve customer satisfaction**

The analysis should first test whether delivery performance is associated with review scores, using the order-level mart and the query comparing delivery delay against the estimated delivery date. This avoids assuming that low satisfaction is caused by delivery before checking the evidence. The key evidence to report is the average review score for orders delivered early/on time versus orders delivered late, along with the size of each group. Include the observed values from the query and the review-score chart before final submission.

**Recommendation:** establish a weekly delivery-exception review for sellers/carriers and prioritise orders predicted to miss the estimated delivery date. Track on-time delivery rate and average review score together; segment results by customer state and seller where possible. After four weeks, compare the late-delivery share and review score with the baseline to determine whether the intervention is working.

**Decision requested:** approve a four-week pilot and a weekly dashboard review. The final memo must replace this evidence placeholder with the actual query results; do not claim causation from correlation.
