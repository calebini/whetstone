# Parcel Queue

## Purpose

Parcel Queue retains jobs until workers acknowledge successful delivery.

## Delivery

A worker MUST wait at least 30 seconds before retrying an unacknowledged job.
A worker MUST reuse the original job ID on every retry.

## Storage

The queue MUST persist a job before reporting that it was accepted.
Acknowledged jobs MUST remain queryable for 24 hours.
