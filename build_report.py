from pathlib import Path
import sqlite3

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)

ROOT = Path(__file__).resolve().parent
DB = ROOT / "olist.db"
CHARTS = ROOT / "reports" / "generated"
OUT = ROOT / "reports" / "Olist_Weekly_Business_Review.pdf"

if not DB.exists():
    raise SystemExit(f"Database not found: {DB}. Run pipeline.py first.")
if not CHARTS.exists():
    raise SystemExit(f"Charts folder not found: {CHARTS}. Run make_charts.py first.")

# ---------- Read actual figures from the local database ----------
with sqlite3.connect(DB) as conn:
    orders = conn.execute("SELECT COUNT(*) FROM stg_orders").fetchone()[0]
    items = conn.execute("SELECT COUNT(*) FROM stg_items").fetchone()[0]
    unique_customers = conn.execute(
        "SELECT COUNT(DISTINCT customer_unique_id) FROM stg_customers "
        "WHERE customer_unique_id IS NOT NULL"
    ).fetchone()[0]

    checks = [
        ("Null order IDs", """
            SELECT COUNT(*) FROM stg_orders
            WHERE order_id IS NULL OR TRIM(order_id) = ''
        """),
        ("Duplicate order ID groups", """
            SELECT COUNT(*) FROM (
                SELECT order_id FROM stg_orders
                GROUP BY order_id HAVING COUNT(*) > 1
            )
        """),
        ("Delivery before purchase", """
            SELECT COUNT(*) FROM stg_orders
            WHERE order_delivered_customer_date IS NOT NULL
              AND order_purchase_timestamp IS NOT NULL
              AND julianday(order_delivered_customer_date)
                  < julianday(order_purchase_timestamp)
        """),
        ("Orders without matching customer", """
            SELECT COUNT(*) FROM stg_orders o
            LEFT JOIN stg_customers c ON o.customer_id = c.customer_id
            WHERE c.customer_id IS NULL
        """),
        ("Payment/item + freight mismatches (> R$1)", """
            WITH item_totals AS (
                SELECT order_id, SUM(price) + SUM(freight_value) AS expected
                FROM stg_items GROUP BY order_id
            ),
            payment_totals AS (
                SELECT order_id, SUM(payment_value) AS paid
                FROM stg_payments GROUP BY order_id
            )
            SELECT COUNT(*)
            FROM item_totals i JOIN payment_totals p USING (order_id)
            WHERE ABS(i.expected - p.paid) > 1.0
        """),
        ("Invalid review scores", """
            SELECT COUNT(*) FROM stg_reviews
            WHERE review_score IS NOT NULL
              AND review_score NOT BETWEEN 1 AND 5
        """),
    ]
    check_results = [
        (label, conn.execute(sql).fetchone()[0]) for label, sql in checks
    ]

    repeat = conn.execute("""
        WITH customer_orders AS (
            SELECT customer_unique_id, COUNT(DISTINCT order_id) AS order_count
            FROM mart_order_summary
            WHERE customer_unique_id IS NOT NULL
            GROUP BY customer_unique_id
        )
        SELECT
            COUNT(*) AS distinct_customers,
            SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
            100.0 * SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0) AS repeat_rate
        FROM customer_orders
    """).fetchone()

    status_counts = conn.execute("""
        SELECT order_status, COUNT(*)
        FROM stg_orders
        GROUP BY order_status
        ORDER BY COUNT(*) DESC
    """).fetchall()

# ---------- Document styles ----------
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ReportTitle", parent=styles["Title"],
    alignment=TA_CENTER, fontName="Helvetica-Bold",
    fontSize=17, leading=21, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="ReportSubtitle", parent=styles["Normal"],
    alignment=TA_CENTER, fontSize=9, leading=12,
    textColor=colors.HexColor("#4B5563"), spaceAfter=10
))
styles.add(ParagraphStyle(
    name="SectionHeading", parent=styles["Heading2"],
    fontName="Helvetica-Bold", fontSize=11.5, leading=14,
    spaceBefore=5, spaceAfter=5, keepWithNext=True
))
styles.add(ParagraphStyle(
    name="BodyTextSmall", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=8.3, leading=11, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="CellText", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=7.4, leading=9.2
))
styles.add(ParagraphStyle(
    name="CellHeader", parent=styles["BodyText"],
    fontName="Helvetica-Bold", fontSize=7.4, leading=9.2,
    textColor=colors.HexColor("#172B4D")
))
styles.add(ParagraphStyle(
    name="Caption", parent=styles["BodyText"],
    fontName="Helvetica-Oblique", fontSize=7.2, leading=9,
    alignment=TA_CENTER, spaceAfter=3
))
styles.add(ParagraphStyle(
    name="MemoText", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=8.5, leading=11.5, spaceAfter=6
))
styles.add(ParagraphStyle(
    name="SmallNote", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=7.4, leading=9.5,
    textColor=colors.HexColor("#374151"), spaceAfter=4
))

def para(text, style="BodyTextSmall"):
    return Paragraph(text, styles[style])

def make_table(rows, widths, header=True, font_size=7.4):
    """Create a table with Paragraph cells so long text wraps instead of overlapping."""
    converted = []
    for row_index, row in enumerate(rows):
        cell_style = "CellHeader" if header and row_index == 0 else "CellText"
        converted.append([
            Paragraph(str(value), styles[cell_style]) for value in row
        ])
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0,
                  hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5EEF6")))
        if len(rows) > 1:
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1),
                             [colors.white, colors.HexColor("#F8FAFC")]))
    table.setStyle(TableStyle(commands))
    return table

# ---------- Build a clean 3-page report (within the 5-page maximum) ----------
doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    rightMargin=1.45 * cm, leftMargin=1.45 * cm,
    topMargin=1.25 * cm, bottomMargin=1.25 * cm,
    title="Olist Weekly Business Review",
    author="Student"
)
story = []

# PAGE 1: Pipeline and data quality
story.extend([
    para("WEEKLY BUSINESS REVIEW", "ReportTitle"),
    para("Brazilian E-Commerce Marketplace | Olist Public Dataset (2016–2018)", "ReportSubtitle"),
    para("1. Pipeline overview", "SectionHeading"),
    para(
        "The Python ELT pipeline loads seven source CSV files into raw tables, creates "
        "staging tables with parsed timestamps and numeric fields, and builds "
        "<b>mart_order_summary</b> at one row per order. Item and payment amounts are "
        "aggregated by order before joining customer and order attributes. Target tables "
        "are replaced on each run to avoid appending duplicate rows; processing and "
        "validation outcomes are logged."
    ),
    para(
        f"<b>Loaded data:</b> {orders:,} orders; {items:,} order-item rows; "
        f"{unique_customers:,} distinct non-null customer identifiers "
        "(<font name='Courier'>customer_unique_id</font>)."
    ),
    para("2. Data-quality results", "SectionHeading"),
])

quality_rows = [["Check", "Failures", "Treatment / interpretation"]]
for label, count in check_results:
    if "Payment" in label:
        treatment = (
            "Flag for investigation. Preserve original records; do not disable the "
            "check or assume the cause without further evidence."
        )
    elif count == 0:
        treatment = "No failures observed in this run."
    else:
        treatment = "Investigate affected records; do not silently modify source data."
    quality_rows.append([label, f"{count:,}", treatment])

story.append(make_table(
    quality_rows,
    [4.4 * cm, 1.7 * cm, 10.0 * cm]
))
story.extend([
    Spacer(1, 7),
    para(
        "<b>Payment reconciliation note:</b> the check compares summed payment value "
        "with summed item price plus freight and flags differences greater than R$1. "
        "It identified 249 order groups. These records are retained and flagged; the "
        "underlying cause has not yet been established. The pipeline currently raises "
        "a quality alarm for this condition, so the run should not be described as "
        "fully passing all quality checks."
    ),
    para("3. Pipeline reliability", "SectionHeading"),
    para(
        "<b>Idempotency:</b> the pipeline replaces raw, staging and mart tables rather "
        "than appending rows. <b>Failure handling:</b> missing files or required columns "
        "raise errors; quality-check failures are logged and cause a non-zero exit. "
        "A successful table build and a successful quality validation are separate outcomes."
    ),
    PageBreak()
])

# PAGE 2: Metrics and charts
story.extend([
    para("4. Metrics and analytical highlights", "SectionHeading"),
    para(
        f"<b>Repeat-customer rate:</b> {repeat[2]:.2f}% "
        f"({int(repeat[1]):,} repeat customers out of {int(repeat[0]):,} distinct "
        "customers). A repeat customer is defined as a customer_unique_id with at "
        "least two distinct orders."
    ),
    para(
        "<b>Revenue definition:</b> merchandise revenue is the sum of item price, "
        "excluding freight. The monthly revenue query excludes canceled and unavailable "
        "orders. Month-over-month growth is (current month revenue − previous month "
        "revenue) / previous month revenue × 100. Growth can be unusually large when "
        "the previous month has very low revenue."
    ),
])
metric_rows = [
    ["Metric", "Formula", "Purpose"],
    ["North Star: fulfilled order rate",
     "Delivered orders ÷ all orders × 100",
     "Tracks the share of orders successfully fulfilled."],
    ["Merchandise revenue",
     "SUM(item price) for eligible orders",
     "Measures merchandise sales, excluding freight."],
    ["On-time delivery rate",
     "Delivered orders with actual date ≤ estimated date ÷ delivered orders with both dates × 100",
     "Tracks delivery reliability."],
    ["Average review score",
     "AVG(valid review_score)",
     "Customer-experience guardrail."],
    ["Repeat-customer rate",
     "Customers with ≥2 orders ÷ distinct customer_unique_id × 100",
     "Tracks customer retention."],
]
story.append(make_table(
    metric_rows,
    [3.4 * cm, 7.2 * cm, 5.5 * cm]
))
story.extend([
    Spacer(1, 7),
    para("5. Charts", "SectionHeading"),
    para(
        "The charts below are generated from the local SQLite database. Review scores "
        "and delivery-delay groups are descriptive; small groups should not be "
        "overinterpreted."
    ),
])

# 2x2 chart grid: balanced dimensions and captions, avoiding a long stack of charts.
chart_specs = [
    ("01_monthly_revenue.png", "Figure 1. Monthly merchandise revenue"),
    ("02_review_scores.png", "Figure 2. Review-score distribution"),
    ("03_delay_vs_review.png", "Figure 3. Review score by delivery delay"),
    ("04_state_revenue.png", "Figure 4. Top 10 states by merchandise revenue"),
]
chart_cells = []
for filename, caption in chart_specs:
    path = CHARTS / filename
    if path.exists():
        img = Image(str(path), width=7.25 * cm, height=4.15 * cm, kind="proportional")
        chart_cells.append([img, para(caption, "Caption")])
    else:
        chart_cells.append([para(f"Missing chart: {filename}", "SmallNote")])

chart_table_data = [
    [chart_cells[0], chart_cells[1]],
    [chart_cells[2], chart_cells[3]],
]
chart_table = Table(chart_table_data, colWidths=[7.75 * cm, 7.75 * cm], hAlign="LEFT")
chart_table.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.extend([chart_table, PageBreak()])

# PAGE 3: Memo and limitations
story.extend([
    para("6. Memo to the Vice President", "SectionHeading"),
    para("<b>Subject: A measured pilot to improve delivery reliability</b>", "MemoText"),
    para(
        "The order-level analysis combines actual delivery timestamps, estimated "
        "delivery timestamps and review scores to examine whether delivery performance "
        "is associated with customer satisfaction. The operational review should compare "
        "the number of late orders with on-time/early orders and their average review "
        "scores, then identify seller or geographic segments with frequent delivery "
        "exceptions. These comparisons show association, not proof of causation.",
        "MemoText"
    ),
    para(
        "<b>Recommendation:</b> run a four-week delivery-exception pilot. Prioritise "
        "orders predicted to miss their estimated delivery dates, review exception "
        "segments weekly, and track on-time delivery rate and average review score "
        "against a documented baseline. Expand the intervention only if the observed "
        "metrics improve without degrading other service measures.",
        "MemoText"
    ),
    para(
        "<b>Decision requested:</b> approve the four-week pilot and weekly monitoring. "
        "Keep the payment-reconciliation alarm visible until the 249 mismatches have "
        "been investigated and the validation rule has been confirmed.",
        "MemoText"
    ),
    para("7. SQL analysis delivered", "SectionHeading"),
    para(
        "The project includes SQL queries for (1) monthly revenue and month-over-month "
        "growth, (2) top-three product categories by customer state, (3) a seven-calendar-day "
        "rolling average of daily orders, (4) repeat-customer rate using customer_unique_id, "
        "and (5) delivery delay relative to estimate versus average review score."
    ),
    para(
        "<b>Limitations:</b> the Olist dataset is observational and covers 2016–2018. "
        "Merchandise revenue is not profit. Delivery/review relationships can be affected "
        "by order mix, seller, geography and other factors. The payment discrepancies "
        "remain unresolved and should be presented as a known data-quality issue.",
        "SmallNote"
    ),
])

def footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(1.45 * cm, 0.65 * cm, "Olist Weekly Business Review")
    canvas.drawRightString(A4[0] - 1.45 * cm, 0.65 * cm, f"Page {document.page}")
    canvas.restoreState()

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(f"Report created: {OUT}")
print("Open the PDF and confirm all three pages are readable before submission.")
