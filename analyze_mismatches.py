import sqlite3
import csv
from pathlib import Path

DB_PATH = Path("olist.db")
OUTPUT_DIR = Path("logs/payment_diagnostics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOP_N = 10

TOP_MISMATCHES_QUERY = """
WITH item_totals AS (
    SELECT
        order_id,
        COUNT(*) AS item_count,
        ROUND(SUM(price), 2) AS item_revenue,
        ROUND(SUM(freight_value), 2) AS freight_total,
        ROUND(SUM(price) + SUM(freight_value), 2) AS expected_total
    FROM stg_items
    GROUP BY order_id
),
payment_totals AS (
    SELECT
        order_id,
        COUNT(*) AS payment_rows,
        ROUND(SUM(payment_value), 2) AS paid_total
    FROM stg_payments
    GROUP BY order_id
)
SELECT
    i.order_id,
    i.item_count,
    COALESCE(p.payment_rows, 0) AS payment_rows,
    i.item_revenue,
    i.freight_total,
    i.expected_total,
    COALESCE(p.paid_total, 0) AS paid_total,
    ROUND(
        i.expected_total - COALESCE(p.paid_total, 0),
        2
    ) AS difference,
    ROUND(
        ABS(i.expected_total - COALESCE(p.paid_total, 0)),
        2
    ) AS absolute_difference
FROM item_totals i
LEFT JOIN payment_totals p
    ON i.order_id = p.order_id
WHERE ABS(
    i.expected_total - COALESCE(p.paid_total, 0)
) > 1.00
ORDER BY absolute_difference DESC
LIMIT ?;
"""
def write_csv(file_path, rows):
    if not rows:
        print(f"No records to write: {file_path}")
        return

    columns = list(rows[0].keys())

    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows([dict(row) for row in rows])

    print(f"Created: {file_path}")


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH.resolve()}")
        print("Run this script from your project root directory.")
        return

    connection = sqlite3.connect(str(DB_PATH))
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.cursor()

        # Verify that the required tables exist.
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """)

        tables = {row["name"] for row in cursor.fetchall()}

        required_tables = {"stg_items", "stg_payments"}
        missing_tables = required_tables - tables

        if missing_tables:
            print("ERROR: Required tables are missing:", missing_tables)
            print("Available tables:", sorted(tables))
            return

        # Count all mismatched orders using the existing threshold.
        count_query = """
        WITH item_totals AS (
            SELECT
                order_id,
                SUM(price) + SUM(freight_value) AS expected_total
            FROM stg_items
            GROUP BY order_id
        ),
        payment_totals AS (
            SELECT
                order_id,
                SUM(payment_value) AS paid_total
            FROM stg_payments
            GROUP BY order_id
        )
        SELECT COUNT(*) AS mismatch_count
        FROM item_totals i
        JOIN payment_totals p
            ON i.order_id = p.order_id
        WHERE ABS(i.expected_total - p.paid_total) > 1.00;
        """

        cursor.execute(count_query)
        mismatch_count = cursor.fetchone()["mismatch_count"]

        print("=" * 65)
        print("PAYMENT RECONCILIATION DIAGNOSTICS")
        print("=" * 65)
        print(f"Existing mismatch count: {mismatch_count}")

        # Retrieve the largest mismatches.
        cursor.execute(TOP_MISMATCHES_QUERY, (TOP_N,))
        top_rows = cursor.fetchall()

        print(f"\nTop {TOP_N} mismatches:")
        print("-" * 65)

        for row in top_rows:
            print(
                f"Order: {row['order_id']}\n"
                f"  Items: {row['item_count']}\n"
                f"  Payment rows: {row['payment_rows']}\n"
                f"  Item revenue: {row['item_revenue']}\n"
                f"  Freight: {row['freight_total']}\n"
                f"  Expected total: {row['expected_total']}\n"
                f"  Paid total: {row['paid_total']}\n"
                f"  Difference: {row['difference']}\n"
            )

        # Export the summary.
        write_csv(
            OUTPUT_DIR / "top10_mismatches.csv",
            top_rows
        )

        # Export raw item and payment records for inspection.
        for row in top_rows:
            order_id = row["order_id"]

            cursor.execute(
                """
                SELECT *
                FROM stg_items
                WHERE order_id = ?
                ORDER BY order_item_id
                """,
                (order_id,)
            )

            items = cursor.fetchall()

            cursor.execute(
                """
                SELECT *
                FROM stg_payments
                WHERE order_id = ?
                ORDER BY payment_sequential
                """,
                (order_id,)
            )

            payments = cursor.fetchall()

            safe_order_id = "".join(
                char if char.isalnum() or char in "-_"
                else "_"
                for char in str(order_id)
            )

            write_csv(
                OUTPUT_DIR / f"items_{safe_order_id}.csv",
                items
            )

            write_csv(
                OUTPUT_DIR / f"payments_{safe_order_id}.csv",
                payments
            )

        print("\nDiagnostics completed.")
        print(f"Output directory: {OUTPUT_DIR.resolve()}")
        print("\nNo source data or pipeline files were modified.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()