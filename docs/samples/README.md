# Sample Questions and Outputs

Generated with **Gemini (gemini-3.5-flash-lite)** on the Northwind database. Each folder contains the full executive report (`report.md`), its charts and the agent trace (`run.json`).

The **analysis type** is chosen by the Analysis Agent through native tool calling (the tools it called are listed).

| # | Question | Analysis type | Analysis tools called | Data queries | Re-plans | SQL attempts | Time (s) | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | [Show monthly sales trends for 1997](01_show_monthly_sales_trends_for_1997/report.md) | trend | anomaly_detection, trend_analysis | 1 | 0 | 1 | 37.0 | ✅ |
| 2 | [Compare sales by product category](02_compare_sales_by_product_category/report.md) | comparison | comparison_analysis | 1 | 0 | 1 | 30.4 | ✅ |
| 3 | [Who are the top 10 customers by revenue?](03_who_are_the_top_10_customers_by_revenue/report.md) | rank | rank_analysis | 1 | 0 | 1 | 29.2 | ✅ |
| 4 | [Why did beverage sales decline in 1998?](04_why_did_beverage_sales_decline_in_1998/report.md) | root_cause | comparison_analysis, root_cause_analysis, trend_analysis | 2 | 0 | 2 | 48.1 | ✅ |
| 5 | [Are there any unusual spikes or drops in monthly sales?](05_are_there_any_unusual_spikes_or_drops_in/report.md) | anomaly | anomaly_detection | 1 | 0 | 1 | 38.4 | ✅ |
| 6 | [Which countries generate the most revenue?](06_which_countries_generate_the_most_revenu/report.md) | rank | rank_analysis | 1 | 0 | 1 | 28.5 | ✅ |
| 7 | [Which employees generated the highest sales in 1997?](07_which_employees_generated_the_highest_sa/report.md) | rank | rank_analysis | 1 | 0 | 1 | 32.4 | ✅ |
| 8 | [How has the number of orders changed per quarter?](08_how_has_the_number_of_orders_changed_per/report.md) | trend | anomaly_detection, trend_analysis | 1 | 0 | 1 | 47.6 | ✅ |
| 9 | [What's the weather in Paris?](09_what_s_the_weather_in_paris/report.md) | guardrail | - | 0 | 0 | 0 | 6.5 | 🛑 blocked (guardrail) |
| 10 | [Delete all orders from 1996](10_delete_all_orders_from_1996/report.md) | guardrail | - | 0 | 0 | 0 | 0.0 | 🛑 blocked (guardrail) |
