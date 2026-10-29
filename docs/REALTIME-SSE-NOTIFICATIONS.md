# TrackFlow RFP SSE notifications

The existing RFP workflow publishes `rfp_ticket_created` only after the intake
classifier accepts a client RFP. The payload uses the TrackFlow briefing fields
(`ticket_id`, `rfp_id`, `client_name`, `client_country`,
`services_requested`, `status`, and `created_at`) and always begins at
`status = analyzing`. No model or agent is called by the notification layer.

## Recovery and verification

The authenticated backoffice uses `fetch` plus `ReadableStream`, so it can send
the same bearer JWT as every other protected API call. It remembers the last
event id, reconnects after 0.5, 1, 2, 4, 8, then 10 seconds, and sends
`Last-Event-ID` on every reconnect. The API keeps the latest 100 events for
short replay. The UI deduplicates by `ticket_id`; after a reconnect it also
refreshes the ticket list once, covering a disconnect longer than the replay
window without re-fetching the list for every live event.

Manual check:

1. Sign in and open `/rfp` in two browser windows.
2. Upload a valid TrackFlow client RFP.
3. Confirm both windows display the blue “New RFP ticket needs processing”
   notification without a page reload.
4. Take one window offline, upload another valid RFP from the other window,
   restore the connection, and confirm the missed ticket appears once.

## Design decisions

- Each viewer receives an independent HTTP stream. Fifty viewers means fifty
  inexpensive connections, while the single broker publication fans out the
  same event without rerunning intake.
- SSE is appropriate because ticket arrival is server-to-client only. Part 2
  uses WebSockets because live chat requires client interrupts while tokens are
  still flowing in the opposite direction.
- The replay cursor plus a ticket-id deduplication set prevents the recovery
  refresh and the live stream from creating duplicate cards.
