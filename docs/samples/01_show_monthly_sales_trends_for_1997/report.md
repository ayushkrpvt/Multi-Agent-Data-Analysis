# Monthly Sales Trends for 1997

**Question:** Show monthly sales trends for 1997  
**Analysis type:** trend  
**Generated:** 2026-11-19 00:18 · **LLM:** Gemini (gemini-3.5-flash-lite) · **Dataset:** Northwind

## Business Summary

Monthly sales for 1997 demonstrated an overall upward trend with significant volatility across the 12-month period. Sales averaged 54,865.73 per month, ultimately growing 16.17% from January to December and culminating in a peak month of 77,476.26 in December.

## Key Findings

- Peak sales occurred in December 1997 at a value of 77,476.26.
- The lowest sales month was June 1997 at 39,088.00.
- Overall sales grew by 16.17% from the first period (January 1997) to the last period (December 1997).
- Average monthly sales across the 12-period span equaled 54,865.73.
- The biggest monthly increase was recorded in December 1997 at 68.74%.
- The biggest monthly decrease occurred in February 1997 at -38.21%.

## Visualizations

### Sales trend by Month

![Sales trend by Month](charts/sales_trend_by_month.png)

_Metric over time (one line per member when a dimension is present)._

## Root Cause Analysis

- Q4 holiday buying surges drove record sales performance in October and December.
- A sharp post-January drop occurred in February (-38.21%), followed by a subsequent summer slump down to 39,088.00 in June.
- Dataset contains orders from 1996-07-04 to 1998-05-06 only, meaning 1997 represents a complete 12-month period but requires full-year context when comparing across other years.

## Recommendations

| Priority | Action | Rationale |
|---|---|---|
| High | Scale up inventory and staffing in Q4 to capitalize on peak demand periods like October and December. | December reached a peak of 77,476.26 with a massive 68.74% monthly increase driven by the Q4 holiday buying surge. |
| Medium | Deploy targeted marketing campaigns or promotions during historically slow summer months such as June. | Mid-year performance dropped sharply in June down to 39,088.00 before recovering. |
| Medium | Investigate the root causes of the sharp post-January drop in February (-38.21%). | February experienced the biggest monthly decrease in the entire year, indicating potential post-holiday customer fatigue. |

## Data Caveats

- Dataset contains orders from 1996-07-04 to 1998-05-06 only; 1997 is a complete 12-month period but should be evaluated alongside full-year context when available.

## Suggested Next Questions

- Which specific product categories drove the massive spikes in October and December 1997?
- What factors contributed to the sharp drop in sales during June 1997?

---
## Appendix: How This Answer Was Produced

### 1. Intent (Intent Agent)
```json
{
  "business_question": "Show monthly sales trends for 1997",
  "metric": "Sales",
  "kpis": [
    "Sales"
  ],
  "dimensions": [
    "Month"
  ],
  "filters": [],
  "time_period": "1997",
  "time_granularity": "month",
  "analysis_type": "trend",
  "required_tables": [
    "orders",
    "order_details"
  ]
}
```

### 2. Execution Plan (Planning Agent)
**Objective:** Show monthly sales trends for the year 1997

1. Extract monthly sales data for 1997
2. Calculate Sales per month
3. Identify peak and lowest sales months
4. Flag any notable growth or decline trends

### 3. Data Retrieval (SQL Agent)

**primary** - Monthly sales for 1997 (12 rows, 1 attempt(s))

```sql
SELECT strftime('%Y-%m', o.OrderDate) AS Month, ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS Sales FROM orders o JOIN order_details od ON o.OrderID = od.OrderID WHERE strftime('%Y', o.OrderDate) = '1997' GROUP BY strftime('%Y-%m', o.OrderDate) ORDER BY Month
```

| Month   |     Sales |
|:--------|----------:|
| 1997-01 | 66,692.80 |
| 1997-02 | 41,207.20 |
| 1997-03 | 39,979.90 |
| 1997-04 | 55,699.39 |
| 1997-05 | 56,823.70 |
| 1997-06 | 39,088.00 |
| 1997-07 | 55,464.93 |
| 1997-08 | 49,981.69 |
| 1997-09 | 59,733.02 |
| 1997-10 | 70,328.50 |

### 4. Agent Trace

| # | Agent | Step | Status | Time (s) |
|---|---|---|---|---|
| 1 | Intent Agent | understand question | ok | 5.7 |
| 2 | Planning Agent | create execution plan | ok | 5.31 |
| 3 | SQL Agent | generate SQL | ok | 2.85 |
| 4 | SQL Agent | validate SQL | ok | 0.02 |
| 5 | SQL Agent | execute SQL | ok | 0.03 |
| 6 | Analysis Agent | profile data & choose analysis | ok | 0.01 |
| 7 | Analysis Agent | trend analysis | ok | 2.91 |
