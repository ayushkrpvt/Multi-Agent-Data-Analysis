# Monthly Sales Anomaly Analysis Executive Report

**Question:** Are there any unusual spikes or drops in monthly sales?  
**Analysis type (chosen by Analysis Agent):** anomaly  
**Generated:** 2026-11-23 00:20 · **LLM:** Gemini (gemini-3.5-flash-lite) · **Dataset:** Northwind

## Business Summary

Anomaly detection identified one significant unusual sales spike in April 1998, reaching $134,630.56, which is 121.94% above the baseline mean of $60,661.81. No other months triggered anomaly thresholds across the analyzed 23 periods. May 1998 represents a partial period containing data up to May 6 and was excluded from baseline calculations to prevent misleading decline interpretations.

## Key Findings

- April 1998 sales reached $134,630.56, representing a 121.94% increase above the baseline mean.
- The baseline mean monthly sales across the dataset is $60,661.81 with a standard deviation of $28,030.63.
- April 1998 achieved a z-score of 2.64, placing it well outside the upper IQR fence of $111,742.19.
- May 1998 contains partial data of $19,898.66 through May 6 and was excluded from baseline comparisons.
- The dataset spans 23 monthly data points from July 1996 through early May 1998.

## Visualizations

### Anomaly detection: Sales

![Anomaly detection: Sales](charts/anomaly_detection_sales.png)

_Values outside the normal range are highlighted._

## Root Cause Analysis

- The April 1998 sales surge to $134,630.56 points to a major one-time sales event, promotional push, or large bulk customer order during that specific month.
- Data coverage limitations restrict the analysis window from July 4, 1996, to May 6, 1998, meaning 1996 and 1998 represent partial operating years.
- May 1998 data is restricted to early-month orders ending May 6, accounting for the lower recorded total of $19,898.66 which should not be interpreted as a sudden market contraction.

## Recommendations

| Priority | Action | Rationale |
|---|---|---|
| High | Investigate the specific customer accounts and product categories responsible for the April 1998 order spike of $134,630.56. | Understanding the drivers behind the z-score 2.64 anomaly helps replicate successful large-scale sales events or bulk purchasing patterns. |
| Medium | Complete the remaining May 1998 data collection before evaluating month-over-month performance trends for Q2. | May 1998 is currently a partial period ($19,898.66 through May 6) and was excluded from baseline calculations to avoid false conclusions of a decline. |
| High | Analyze the sustained sales elevation observed throughout early 1998, where monthly sales consistently exceeded $100,000 (Jan to Apr). | April sales reached $134,630.56, and preceding months like January ($100,854.72), February ($104,561.95), and March ($109,825.45) indicate a broader structural growth trend above the $60,661.81 baseline mean. |

## Data Caveats

- 1998-05 is a partial period and was excluded from the baseline calculations.

## Suggested Next Questions

- Which specific customers or orders drove the record $134,630.56 sales figure in April 1998?
- What factors contributed to the sustained high sales figures exceeding $100,000 in January, February, March, and April of 1998 compared to earlier periods in 1996 and 1997?
- How do complete May sales figures compare once the full month of data is made available?

---
## Appendix: How This Answer Was Produced

### 1. Intent (Intent Agent)
```json
{
  "business_question": "Are there any unusual spikes or drops in monthly sales?",
  "metric": "Sales",
  "kpis": [
    "Sales",
    "Orders"
  ],
  "dimensions": [
    "Month"
  ],
  "filters": [],
  "time_period": "All",
  "time_granularity": "month",
  "required_tables": [
    "orders",
    "order_details"
  ]
}
```

### 2. Execution Plan (Planning Agent)
**Objective:** Identify unusual spikes or drops in monthly sales and order volume across the Northwind database timeline.

1. Retrieve monthly sales and order count across all available months
2. Identify any significant spikes or drops in the timeline
3. Summarize findings highlighting anomaly months

### 3. Data Retrieval (SQL Agent)

**primary** - Retrieve total monthly sales and order count for all months in the database (23 rows, 1 attempt(s))

```sql
SELECT 
    strftime('%Y-%m', o.OrderDate) AS Month,
    ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS Sales,
    COUNT(DISTINCT o.OrderID) AS Orders
FROM orders o
JOIN order_details od ON o.OrderID = od.OrderID
GROUP BY strftime('%Y-%m', o.OrderDate)
ORDER BY Month ASC
```

| Month   |     Sales |   Orders |
|:--------|----------:|---------:|
| 1996-07 | 30,192.10 |       22 |
| 1996-08 | 26,609.40 |       25 |
| 1996-09 | 27,636.00 |       23 |
| 1996-10 | 41,203.60 |       26 |
| 1996-11 | 49,704.00 |       25 |
| 1996-12 | 50,953.40 |       31 |
| 1997-01 | 66,692.80 |       33 |
| 1997-02 | 41,207.20 |       29 |
| 1997-03 | 39,979.90 |       30 |
| 1997-04 | 55,699.39 |       31 |

### 5. Native Tool Calls

| # | Agent | Tool | Arguments |
|---|---|---|---|
| 1 | Intent Agent | `submit_intent` | {"time_granularity": "month", "kpis": ["Sales", "Orders"], "filters": [], "time_period": "All", "metric": "Sales", "busi |
| 2 | Planning Agent | `submit_plan` | {"data_queries": [{"purpose": "Retrieve total monthly sales and order count for all months in the database", "id": "prim |
| 3 | SQL Agent | `submit_sql_query` | {"tables_used": ["orders", "order_details"], "sql": "SELECT \n    strftime('%Y-%m', o.OrderDate) AS Month,\n    ROUND(SU |
| 4 | Analysis Agent | `anomaly_detection` | {"dataset_id": "primary", "z_threshold": 2} |
| 5 | Analysis Agent | `submit_analysis` | {"summary": "Anomaly detection identified a significant unusual spike in monthly sales for April 1998, reaching $134,630 |

### 6. Agent Trace

| # | Agent | Step | Status | Time (s) |
|---|---|---|---|---|
| 1 | Intent Agent | understand question + guardrails | ok | 2.02 |
| 2 | Planning Agent | create execution plan | ok | 6.71 |
| 3 | SQL Agent | generate SQL | ok | 1.46 |
| 4 | SQL Agent | validate SQL | ok | 0.01 |
| 5 | SQL Agent | execute SQL | ok | 0.02 |
| 6 | Analysis Agent | choose analysis via tool calling | ok | 6.94 |
