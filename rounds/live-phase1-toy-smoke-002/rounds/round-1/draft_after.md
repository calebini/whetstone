# Toy Notification Spec

## Purpose

Send a notification when a watched file changes.

## Roles

- Watcher: observes file changes.
- Sender: sends notifications.
- Operator: configures the watched file and destination.

## Behavior

The system polls `watch_path` every `poll_interval_seconds`.

### Change Definition

A file is considered **changed** when the SHA-256 hash of its byte content differs from the hash recorded for the previous poll cycle.

### First-Run Baseline

On the first poll cycle after startup, the system records the file's current SHA-256 hash as the baseline and MUST NOT send a notification.

### Subsequent Cycles

On each subsequent poll cycle:

1. Read the file bytes from `watch_path`.
2. Compute `sha256_current` over those bytes.
3. If `sha256_current != sha256_previous`, the system MUST send a notification (see **Notification Format**) and then set `sha256_previous = sha256_current`.
4. If `sha256_current == sha256_previous`, no notification is sent.

## Notification Format

- Transport: an email message addressed to `destination`, which MUST be an email address.
- Subject: `ToyNotify: file changed: {watch_path}`
- Body (plain text):
  - `watch_path: {watch_path}`
  - `timestamp_utc: {RFC3339 timestamp}`
  - `sha256: {sha256_current}`

## Configuration

```yaml
watch_path: ./input.txt
destination: ops@example.com
poll_interval_seconds: 60
failure_log_path: ./toy_notify_failures.log
```

## Failure Handling

If sending fails, the system MUST append a single-line JSON object to `failure_log_path` (JSONL format) with keys:

- `timestamp_utc` (RFC3339)
- `watch_path`
- `destination`
- `error`

After recording the failure, the system MUST continue polling on the normal schedule.
