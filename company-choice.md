# Milestone 0 — Company Choice

I chose **TrackFlow**, the last-mile delivery and warehouse management company operating in Mexico and Spain. I am interested in how TrackFlow connects physical warehouse work in Monterrey and Zaragoza with software, carrier data, and customer-facing tracking. Its work with fashion, electronics, and cosmetics brands creates useful problems involving inventory, fragile products, delivery reliability, and returns. I also like that the same company context can grow from a public website into internal operations tools and, later, AI-assisted automation.

## Departments I want to explore

- **Warehouse Operations:** Ana Whitfield's team needs accurate inventory visibility, low-stock alerts, and fewer manual fulfillment decisions across two warehouses.
- **Last Mile and Carrier Management:** Carlos Vega's team must select carriers using destination coverage, package constraints, cost, speed, and reliability instead of relying on disconnected spreadsheets.
- **Reverse Logistics:** Returns inspection and reconditioning create a strong opportunity to automate repetitive classification and routing work while keeping a human in control of exceptions.

The automation challenge I most look forward to is carrier selection and delivery-incident handling. It combines business rules, live operational data, explainable recommendations, and escalation workflows in a way that could measurably improve TrackFlow's delivery performance.

## My AI Agent Idea

I would build a delivery-operations agent that reviews pending shipments and recommends the best eligible carrier. It would need product weight and fragility, shipment destination and priority, carrier coverage and capacity, current rates, and historical on-time performance. The agent would produce an explained recommendation with expected cost and confidence, flag shipments that have no safe carrier, and ask a logistics coordinator for approval before assigning or escalating an exception.
