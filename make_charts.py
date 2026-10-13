import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "generated"
OUT.mkdir(parents=True, exist_ok=True)

DB = ROOT / "olist.db"
if not DB.exists():
    raise SystemExit("olist.db not found. Run pipeline.py first.")

with sqlite3.connect(DB) as con:
    # 1. Monthly merchandise revenue
    monthly = con.execute("""
        SELECT strftime('%Y-%m', order_purchase_timestamp) AS month,
               SUM(item_revenue) AS revenue
        FROM mart_order_summary
        WHERE order_status NOT IN ('canceled', 'unavailable')
        GROUP BY strftime('%Y-%m', order_purchase_timestamp)
        ORDER BY month
    """).fetchall()

    # 2. Review-score distribution
    reviews = con.execute("""
        SELECT review_score, COUNT(*) AS review_count
        FROM mart_order_summary
        WHERE review_score IS NOT NULL
        GROUP BY review_score
        ORDER BY review_score
    """).fetchall()

    # 3. Review scores by delivery timing.
    # Delay = actual delivery timestamp - estimated delivery timestamp.
    # Negative means early; positive means late. Rounded day values are used
    # consistently for labels and ordering.
    delay_bands = con.execute("""
        WITH classified AS (
            SELECT
                CASE
                    WHEN ROUND(delivery_delay_days) < -7
                        THEN 'More than 7 days early'
                    WHEN ROUND(delivery_delay_days) < 0
                        THEN '1-7 days early'
                    WHEN ROUND(delivery_delay_days) = 0
                        THEN 'On time'
                    WHEN ROUND(delivery_delay_days) <= 7
                        THEN '1-7 days late'
                    ELSE 'More than 7 days late'
                END AS delay_band,
                CASE
                    WHEN ROUND(delivery_delay_days) < -7 THEN 1
                    WHEN ROUND(delivery_delay_days) < 0 THEN 2
                    WHEN ROUND(delivery_delay_days) = 0 THEN 3
                    WHEN ROUND(delivery_delay_days) <= 7 THEN 4
                    ELSE 5
                END AS sort_order,
                review_score
            FROM mart_order_summary
            WHERE delivery_delay_days IS NOT NULL
              AND review_score IS NOT NULL
        )
        SELECT
            delay_band,
            COUNT(*) AS order_count,
            ROUND(AVG(review_score), 2) AS average_review_score
        FROM classified
        GROUP BY delay_band, sort_order
        ORDER BY sort_order
    """).fetchall()

    # 4. Top 10 customer states by merchandise revenue
    states = con.execute("""
        SELECT customer_state, SUM(item_revenue) AS revenue
        FROM mart_order_summary
        WHERE customer_state IS NOT NULL
        GROUP BY customer_state
        ORDER BY revenue DESC
        LIMIT 10
    """).fetchall()


def save_bar(data, title, xlabel, ylabel, filename, rotate=0, figsize=(9, 4.8)):
    """Save a readable bar chart and close the figure."""
    if not data:
        print(f"WARNING: No data available for {title}; chart skipped.")
        return

    x, y = zip(*data)
    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(x, y)
    ax.set_title(title, fontsize=12, pad=12)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.tick_params(axis="x", labelrotation=rotate)

    if rotate:
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


# Chart 1: monthly merchandise revenue
save_bar(
    [(month, revenue) for month, revenue in monthly if month and revenue is not None],
    "Monthly Merchandise Revenue",
    "Purchase month",
    "Revenue (BRL)",
    "01_monthly_revenue.png",
    rotate=45,
    figsize=(10, 4.8),
)

# Chart 2: review-score distribution
save_bar(
    [(str(int(score)), count) for score, count in reviews],
    "Distribution of Review Scores",
    "Review score (1 = lowest, 5 = highest)",
    "Number of orders",
    "02_review_scores.png",
    figsize=(8, 4.8),
)

# Chart 3: delivery-delay bands, with average review score and sample size.
if delay_bands:
    labels = [row[0] for row in delay_bands]
    counts = [row[1] for row in delay_bands]
    averages = [row[2] for row in delay_bands]

    fig, ax = plt.subplots(figsize=(9, 5.2))
    bars = ax.bar(labels, averages)
    ax.set_title("Average Review Score by Delivery Timing", fontsize=12, pad=12)
    ax.set_xlabel("Actual delivery compared with estimated date", fontsize=9)
    ax.set_ylabel("Average review score (1–5)", fontsize=9)
    ax.set_ylim(0, 5.7)
    ax.tick_params(axis="x", labelrotation=18, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)

    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")

    for bar, count, average in zip(bars, counts, averages):
        if average is not None:
            ax.annotate(
                f"{average:.2f}\n(n={count:,})",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "03_delay_vs_review.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
else:
    print("WARNING: No delivery-delay/review records available; chart skipped.")

# Chart 4: top 10 states by merchandise revenue
save_bar(
    [(state, revenue) for state, revenue in states],
    "Top 10 Customer States by Merchandise Revenue",
    "Customer state",
    "Revenue (BRL)",
    "04_state_revenue.png",
    figsize=(9, 4.8),
)

print(f"Charts saved to {OUT}")
print("Delivery-delay chart uses rounded day values and displays sample sizes.")
