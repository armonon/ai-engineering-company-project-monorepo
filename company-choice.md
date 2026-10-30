# Company choice: TrackFlow

## Why I chose TrackFlow

I chose TrackFlow because its problems are practical and directly tied to
e-commerce, where a lost or late parcel costs real money. I have shipped
packages that were lost and had to pay for them myself, so I know how
frustrating it is when nobody can say where a parcel is or who is responsible.
The briefing shows TrackFlow has the same gaps internally: its Los Angeles and
Zaragoza warehouses run on different systems with no shared view of inventory,
and every customer question is still answered by a person, even though about
80% of them could be answered automatically. Fixing those problems with AI
would help the brands TrackFlow serves and the people waiting for their orders.

## Departments that interest me

- **Warehouse Operations (Ana Whitfield):** this is where every order starts.
  With two warehouses on different systems, paper picking lists, and
  inventory discrepancies found late, mistakes here spread to every later
  step of the delivery.
- **Customer Experience (Valentina Cruz):** this is where customers feel those
  mistakes. Fifteen agents answer repetitive "where is my parcel?" questions by
  email, WhatsApp, and phone, with no knowledge base and no coverage outside
  office hours.

Together they are two of the most important parts of the puzzle: one keeps
the operation accurate, and the other keeps customers informed and trusting
TrackFlow.

## The challenges I'm most looking forward to

The **unified inventory API** is the most important one to me: one real-time
answer for stock of any SKU in either warehouse, which every dashboard, alert,
and agent can then build on. Next is the **carrier selection engine**, which
recommends the best of TrackFlow's eight carriers for each shipment based on
destination, weight, and urgency, instead of assigning carriers by hand.

## My AI Agent Idea

A first-line customer experience agent that answers "where is my parcel?"
questions for both brands and end consumers, 24/7.

- **What it does:** greets the customer, collects the information it needs
  (tracking number or order ID, and the brand), looks up the shipment, and
  explains its status in plain language. If the information is missing or
  doesn't match, it asks for it instead of guessing.
- **What information it needs:** shipment and tracking events from the
  carriers (UPS, FedEx, DHL, MRW, SEUR), order and SKU data from the unified
  inventory API, and TrackFlow's delivery and returns policies from a
  knowledge base.
- **What it produces or triggers:**
  - a **reply** with the parcel's current status and next step;
  - a **ticket** in the ticketing system recording the conversation; and
  - an **escalation** to a human agent when the parcel is lost, delayed past
    its delivery promise, or the customer is frustrated.
