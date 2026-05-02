# Toy Notification Spec

## Purpose

Send a notification when a watched file changes.

## Roles

- Watcher: observes file changes.
- Sender: sends notifications.
- Operator: configures the watched file and destination.

## Behavior

The system checks `watch_path` every `poll_interval_seconds`.

### Change Detection

A file is considered "changed" at a poll interval if the SHA-256 hash of the file's byte contents differs from the SHA-256 hash recorded at the previous successful read.

### Startup Behavior

On startup, the system attempts to read `watch_path`.

- If the read succeeds, the system records the file's SHA-256 hash as the baseline and MUST NOT send a notification.
- If the read fails, the system records the failure (see Failure Handling), does not establish a baseline, and continues polling.

### Notification

At each poll interval after a baseline is established:

- If the current SHA-256 hash equals the baseline, the system does nothing.
- If the current SHA-256 hash differs from the baseline, the system attempts to send a notification to `destination` and:
  - on success, updates the baseline to the current hash
  - on failure, records the failure and MUST NOT update the baseline

## Configuration

```yaml
watch_path: ./input.txt
destination: ops@example.com
poll_interval_seconds: 60
```

## Failure Handling

The system records failures by appending a newline-delimited JSON (NDJSON) record to `failure.log` in the working directory.

Each failure record MUST include:

- `timestamp`: ISO 8601 timestamp in UTC
- `watch_path`: the configured watch path
- `destination`: the configured destination
- `phase`: one of `read` or `send`
- `error`: a human-readable error string

If reading `watch_path` fails at startup or at any poll interval, the system records a failure with `phase: read` and continues polling.

If sending fails, the system records a failure with `phase: send` and continues polling.
