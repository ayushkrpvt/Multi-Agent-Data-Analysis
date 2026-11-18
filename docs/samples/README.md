# Sample Questions and Outputs

Generated with **Gemini (gemini-3.5-flash-lite)** on the Northwind database. Each folder contains the full executive report (`report.md`), its charts and the agent trace (`run.json`).

| # | Question | Analysis type | Data queries | SQL attempts (all queries) | Time (s) | Status |
|---|---|---|---|---|---|---|
| 1 | [Show monthly sales trends for 1997](01_show_monthly_sales_trends_for_1997/report.md) | trend | 1 | 1 | 57.6 | ✅ |
| 2 | [Compare sales by product category](02_compare_sales_by_product_category/report.md) | comparison | 1 | 1 | 15.6 | ✅ |
| 3 | [Who are the top 10 customers by revenue?](03_who_are_the_top_10_customers_by_revenue/report.md) | comparison | 1 | 1 | 46.9 | ✅ |
| 4 | [Why did beverage sales decline in 1998?](04_why_did_beverage_sales_decline_in_1998/report.md) | root_cause | 2 | 2 | 44.8 | ✅ |
| 5 | [Are there any unusual spikes or drops in monthly sales?](05_are_there_any_unusual_spikes_or_drops_in/report.md) | anomaly | 1 | 1 | 20.4 | ✅ |
| 6 | [Which countries generate the most revenue?](06_which_countries_generate_the_most_revenu/report.md) | comparison | 1 | 1 | 35.0 | ✅ |
| 7 | [Which employees generated the highest sales in 1997?](07_which_employees_generated_the_highest_sa/report.md) | comparison | 1 | 1 | 50.4 | ✅ |
| 8 | [How has the number of orders changed per quarter?](08_how_has_the_number_of_orders_changed_per/report.md) | trend | 1 | 1 | 10.5 | ✅ |
