# Olist Weekly Business Review

A small, reproducible ELT pipeline and SQL analytics project for the Olist Brazilian E-Commerce dataset.

## 1. Dataset setup
Download the CSV files from the Olist dataset page on Kaggle and place the extracted CSVs in `data/`.
Expected filenames (standard Olist names):
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`

The pipeline uses SQLite, so no separate database server is required.

## 2. Setup and run (Windows PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python pipeline.py
python make_charts.py
```
If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `.venv\Scripts\python.exe pipeline.py`.

## 3. Outputs
- `olist.db`: raw tables, staging tables, and `mart_order_summary`
- `logs/pipeline.log`: step logs and failures
- `reports/generated/`: four PNG charts
- `sql/quality/`: SQL checks used by the pipeline
- `sql/analytics/`: five analytical queries

## 4. Idempotency and failure handling
Each run replaces raw/staging/mart tables inside a transaction, so rerunning does not append duplicate records. Missing required files/columns raise a clear exception. Quality checks are executed after building tables; failed checks are logged and cause a non-zero exit. The pipeline does not silently delete anomalous business records.

## 5. Important interpretation notes
- Customer identity across purchases: use `customer_unique_id`, not `customer_id`. `customer_id` is order-level and can change for the same person.
- Revenue definition in this project: sum of order-item `price` (merchandise revenue); freight is tracked separately. Payment total is compared against item price + freight in quality checks.
- The report should quote actual row counts/results from your local run. Do not present sample or assumed numbers as observed findings.
