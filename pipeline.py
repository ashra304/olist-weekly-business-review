import csv
import logging
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
DB = ROOT / "olist.db"
LOGS.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOGS / "pipeline.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

FILES = {
    "orders": ("olist_orders_dataset.csv", {"order_id", "customer_id", "order_status", "order_purchase_timestamp"}),
    "items": ("olist_order_items_dataset.csv", {"order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"}),
    "payments": ("olist_order_payments_dataset.csv", {"order_id", "payment_value"}),
    "reviews": ("olist_order_reviews_dataset.csv", {"order_id", "review_score"}),
    "customers": ("olist_customers_dataset.csv", {"customer_id", "customer_unique_id", "customer_state"}),
    "products": ("olist_products_dataset.csv", {"product_id", "product_category_name"}),
    "sellers": ("olist_sellers_dataset.csv", {"seller_id", "seller_state"}),
}

def load_csv(name, filename, required):
    path = DATA / filename
    if not path.exists():
        raise FileNotFoundError(f"Required input file is missing: {path}")
    # Validate headers before loading the data.
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        headers = set(next(csv.reader(f), []))
    missing = sorted(required - headers)
    if missing:
        raise ValueError(f"{filename} is missing required columns: {missing}")
    logging.info("Loading %s from %s", name, filename)
    return pd.read_csv(path)

def main():
    logging.info("Pipeline started")
    loaded = {}
    for name, (filename, required) in FILES.items():
        loaded[name] = load_csv(name, filename, required)

    with sqlite3.connect(DB) as conn:
        try:
            conn.execute("BEGIN")
            # Replace tables on each run: deterministic and idempotent.
            for name, df in loaded.items():
                df.to_sql(f"raw_{name}", conn, if_exists="replace", index=False)
                logging.info("raw_%s loaded: %s rows", name, len(df))

            # Cleaned staging tables; parse dates and coerce numeric fields.
            for name, df in loaded.items():
                clean = df.copy()
                for col in clean.columns:
                    if col.endswith("_timestamp") or col in ("order_estimated_delivery_date", "order_delivered_customer_date"):
                        clean[col] = pd.to_datetime(clean[col], errors="coerce")
                for col in ("price", "freight_value", "payment_value", "review_score"):
                    if col in clean.columns:
                        clean[col] = pd.to_numeric(clean[col], errors="coerce")
                clean.to_sql(f"stg_{name}", conn, if_exists="replace", index=False)

            conn.executescript("""
            DROP TABLE IF EXISTS mart_order_summary;
            CREATE TABLE mart_order_summary AS
            WITH item_totals AS (
              SELECT order_id, SUM(price) AS item_revenue,
                     SUM(freight_value) AS freight_total,
                     COUNT(*) AS item_count
              FROM stg_items GROUP BY order_id
            ), payment_totals AS (
              SELECT order_id, SUM(payment_value) AS payment_total
              FROM stg_payments GROUP BY order_id
            ), review_scores AS (
              SELECT order_id, AVG(review_score) AS review_score
              FROM stg_reviews GROUP BY order_id
            )
            SELECT o.order_id, o.customer_id, c.customer_unique_id, c.customer_state,
                   o.order_status, o.order_purchase_timestamp,
                   o.order_approved_at, o.order_delivered_customer_date,
                   o.order_estimated_delivery_date,
                   COALESCE(i.item_revenue, 0) AS item_revenue,
                   COALESCE(i.freight_total, 0) AS freight_total,
                   COALESCE(i.item_count, 0) AS item_count,
                   p.payment_total, r.review_score,
                   CASE WHEN o.order_delivered_customer_date IS NOT NULL
                             AND o.order_estimated_delivery_date IS NOT NULL
                        THEN julianday(o.order_delivered_customer_date)
                           - julianday(o.order_estimated_delivery_date)
                        ELSE NULL END AS delivery_delay_days
            FROM stg_orders o
            LEFT JOIN stg_customers c ON o.customer_id = c.customer_id
            LEFT JOIN item_totals i ON o.order_id = i.order_id
            LEFT JOIN payment_totals p ON o.order_id = p.order_id
            LEFT JOIN review_scores r ON o.order_id = r.order_id;
            """)
            # Validate checks and stop on any failures.
            checks = [
              ("null_order_id", "SELECT COUNT(*) FROM stg_orders WHERE order_id IS NULL OR TRIM(order_id) = ''"),
              ("duplicate_order_id", "SELECT COUNT(*) FROM (SELECT order_id FROM stg_orders GROUP BY order_id HAVING COUNT(*) > 1)"),
              ("delivery_before_purchase", """SELECT COUNT(*) FROM stg_orders
                 WHERE order_delivered_customer_date IS NOT NULL AND order_purchase_timestamp IS NOT NULL
                 AND julianday(order_delivered_customer_date) < julianday(order_purchase_timestamp)"""),
              ("orders_without_customer", """SELECT COUNT(*) FROM stg_orders o LEFT JOIN stg_customers c
                 ON o.customer_id=c.customer_id WHERE c.customer_id IS NULL"""),
              ("payment_vs_items_freight", """SELECT COUNT(*) FROM (
                 SELECT i.order_id, SUM(i.price)+SUM(i.freight_value) AS expected,
                        p.payment_total
                 FROM stg_items i JOIN
                   (SELECT order_id, SUM(payment_value) payment_total FROM stg_payments GROUP BY order_id) p
                   ON i.order_id=p.order_id
                 GROUP BY i.order_id
                 HAVING ABS(expected-p.payment_total) > 1.00)"""),
              ("invalid_review_score", "SELECT COUNT(*) FROM stg_reviews WHERE review_score IS NOT NULL AND review_score NOT BETWEEN 1 AND 5"),
            ]
            failures = []
            for label, sql in checks:
                count = conn.execute(sql).fetchone()[0]
                logging.info("QUALITY CHECK %s: %s failing rows/groups", label, count)
                print(f"{label}: {count} failing rows/groups")
                if count:
                    failures.append((label, count))
            conn.commit()
            logging.info("Mart built: %s rows", conn.execute("SELECT COUNT(*) FROM mart_order_summary").fetchone()[0])
            if failures:
                message = "; ".join(f"{name}={count}" for name, count in failures)
                logging.error("Quality alarm: %s", message)
                raise RuntimeError("Data-quality alarm; investigate flagged records: " + message)
        except Exception:
            conn.rollback()
            logging.exception("Pipeline failed")
            raise
    logging.info("Pipeline completed successfully")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
