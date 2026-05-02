# Toy Approval Adapter 1.0

## Purpose

Define a tiny approval adapter for Whetstone live smoke testing.

## Adapter Contract

The adapter records approval requests and returns an approval status.

**Status domain:** `PENDING | APPROVED | REJECTED`

**Request identity:** A request is keyed by its unique `request_id` string.

**Initial status:** Every newly recorded request begins in `PENDING`.

**Duplicate handling:** Submitting a request whose `request_id` already exists returns the current recorded status without creating a new record.

**Determinism rule:** For a given `request_id`, the adapter always returns the status currently recorded for that key. Status transitions (`PENDING → APPROVED` or `PENDING → REJECTED`) are externally driven and recorded atomically; once a terminal status (`APPROVED` or `REJECTED`) is set, it cannot change.