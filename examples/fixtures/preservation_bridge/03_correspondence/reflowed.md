# Dispatch Worker

## Retry Policy

Workers MUST retain the job ID and attempt count across restarts.
Workers MUST retain the job ID and attempt count across restarts.
Workers MUST wait at least 20 seconds before retrying.
Workers MUST preserve the original destination.

## Audit

The worker MUST record each failed attempt before retrying.
