"""
Offline tests (no LLM needed): database, schema, SQL validator, analysis tools, charts.

    python -m pytest tests/test_tools.py -q
"""

from tools import analysis_tool as at
from tools.database_tool import execute_query
from tools.schema_tool import get_sql_context, get_tables, normalize_tables
from tools.sql_validator import clean_sql, validate_sql
from tools.visualization_tool import create_charts

MONTHLY_BY_CATEGORY = """
SELECT strftime('%Y-%m', o.OrderDate) AS Month, c.CategoryName,
       ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS Sales
FROM orders o
JOIN order_details od ON o.OrderID = od.OrderID
JOIN products p ON p.ProductID = od.ProductID
JOIN categories c ON c.CategoryID = p.CategoryID
GROUP BY 1, 2
"""


def test_database_has_northwind_tables():
    tables = get_tables()
    for t in ["orders", "order_details", "products", "categories", "customers"]:
        assert t in tables


def test_schema_context_contains_rules():
    ctx = get_sql_context(["products", "order_details"])
    assert "order_details" in ctx and "Sales" in ctx
    assert normalize_tables(["Orders", "nope"]) == ["orders"]


def test_validator_accepts_select_and_blocks_writes():
    assert validate_sql(MONTHLY_BY_CATEGORY)[0]
    assert validate_sql("SELECT REPLACE(ProductName, 'a', 'b') FROM products")[0]
    assert not validate_sql("DELETE FROM orders")[0]
    assert not validate_sql("SELECT 1; DROP TABLE orders")[0]
    assert not validate_sql("SELECT YEAR(OrderDate) FROM orders")[0]
    assert not validate_sql("SELECT nope FROM orders")[0]
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"


def test_analysis_and_charts(tmp_path):
    df = execute_query(MONTHLY_BY_CATEGORY)
    prof = at.profile(df, "Sales")
    assert prof["time_col"] == "Month" and prof["metric"] == "Sales"

    trend = at.trend_analysis(df, prof)
    assert "1998-05" in trend["partial_periods"]

    comp = at.comparison_analysis(df, prof)
    assert comp["ranking"][0]["CategoryName"] == "Beverages"

    rc = at.root_cause_analysis({"primary": df}, {"primary": prof})
    assert rc["drivers"]["primary"]["like_for_like"]

    charts = create_charts("root_cause", {"primary": df}, {"primary": prof}, rc, "pytest")
    assert charts
