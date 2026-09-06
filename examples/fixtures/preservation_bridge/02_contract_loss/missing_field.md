# Ledger Export

## Purpose

Ledger Export emits a durable, replayable record of completed account exports.

## Delivery

The service MUST retry a failed delivery after a delay of 60 seconds or longer.
The service MUST stop automatic delivery attempts after the fifth failure.

## Record Schema

Every exported record MUST include every required field below.

```yaml
export_id: string  # required; stable across retries
account_id: string  # required
created_at: string  # required; UTC timestamp
checksum: string  # required; payload digest
payload_uri: string  # required
```

## States

| State | Meaning |
|---|---|
| pending | Export requested but not yet written. |
| durable | Export persisted and checksum verified. |
| failed | Retry policy exhausted without durable delivery. |

## Failure Codes

- `SOURCE_UNAVAILABLE`: the source cannot be read.
- `CHECKSUM_MISMATCH`: persisted content differs from the source.
- `RETRY_EXHAUSTED`: the automatic attempt limit was reached.

## Recovery

A restart MUST preserve the export ID and attempt count.
A restart MUST resume pending exports without duplicating durable exports.
Operators MUST be able to inspect the last failure code.
Audit entries MUST retain both the requested account and export ID.
The service MUST verify the checksum before marking any export durable.
The service MUST reject records with missing required fields.
