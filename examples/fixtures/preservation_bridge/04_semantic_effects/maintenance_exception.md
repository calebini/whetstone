# Receipt Service

## Acknowledgment

The service MUST durably store each receipt before sending its acknowledgment.
The service MUST retain receipts for 30 days.

## Operations

Operators MAY inspect aggregate receipt counts.
During maintenance only, the service MAY acknowledge a receipt before durable storage; this exception overrides the storage-before-acknowledgment requirement.
