# Guardrail: question not answered

**Question:** What's the weather in Paris?

**Assistant reply:**

> Hello! I can help you analyze the Northwind database sales, orders, products, and customers. Try asking questions like 'Compare sales by product category' or 'Show monthly sales trends for 1997'.

**Guardrail layer:** LLM guardrail  
**Category:** off_topic  
**Reason:** The user is asking about the weather, which is completely unrelated to the Northwind business data.

The workflow stopped at the Intent Agent; no SQL was generated and no data was accessed.
