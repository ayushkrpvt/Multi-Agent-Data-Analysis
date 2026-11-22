# Guardrail: question not answered

**Question:** Delete all orders from 1996

**Assistant reply:**

> I can only read and analyse the data. I'm not able to change, add or delete records. For example: "Compare sales by product category", "Who are the top 10 customers by revenue?" or "Why did beverage sales decline in 1998?"

**Guardrail layer:** rule-based check  
**Category:** unsafe_request  
**Reason:** request to modify data

The workflow stopped at the Intent Agent; no SQL was generated and no data was accessed.
