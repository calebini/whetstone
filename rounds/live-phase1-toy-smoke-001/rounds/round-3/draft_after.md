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

A file is considered "changed" at a poll interval if the SHA-256 hash of the file byte contents differs from the SHA-256 hash recorded at the previous successful read.

### Startup Behavior

On startup, the system attempts to read `watch_path`.

- If the read succeeds, the system records the SHA-256 hash as the baseline and MUST NOT send a notification.
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
failure_log_path: ./failure.log
event_log_path: ./event.log
```

## Operational Observability

The system MUST provide success-path observability and a liveness signal by writing newline-delimited JSON (NDJSON) records to `event_log_path`.

### Event Records

Each event record MUST include:

- `timestamp`: ISO 8601 combined date-time in UTC formatted as `YYYY-MM-DDTHH:MM:SS.sssZ` (millisecond precision, `Z` suffix)
- `watch_path`: the configured watch path
- `destination`: the configured destination
- `event`: one of `startup_baseline_established`, `poll`, or `notification_sent`

Additional required fields by `event`:

- `startup_baseline_established`:
  - `baseline_hash`: the SHA-256 hash recorded as the baseline
- `poll`:
  - `outcome`: one of `no_baseline`, `read_failed`, `no_change`, or `change_detected`
  - `baseline_established`: boolean
  - `baseline_hash`: the current baseline hash when `baseline_established` is true
  - `current_hash`: the computed hash when the read succeeds
- `notification_sent`:
  - `previous_baseline_hash`: the baseline hash before sending
  - `new_baseline_hash`: the hash that becomes the new baseline after sending

### Liveness

After startup, at each poll interval, the system MUST append exactly one `poll` event record.

## Failure Handling

### Failure Log Destination

The system records failures by appending a newline-delimited JSON (NDJSON) record to the file at `failure_log_path` (default `./failure.log`).

### Failure Records

Each failure record MUST include:

- `timestamp`: ISO 8601 combined date-time in UTC formatted as `YYYY-MM-DDTHH:MM:SS.sssZ` (millisecond precision, `Z` suffix)
- `watch_path`: the configured watch path
- `destination`: the configured destination
- `phase`: one of `read` or `send`
- `error`: a human-readable error string

If reading `watch_path` fails at startup or at any poll interval, the system records a failure with `phase: read` and continues polling.

If sending fails, the system records a failure with `phase: send` and continues polling.

### Log Write Failures

If appending a failure record to `failure_log_path` fails, the system MUST emit the same JSON record to stderr and MUST continue polling.

If appending an event record to `event_log_path` fails, the system MUST emit the same JSON record to stderr and MUST continue polling.

### Retention and Rotation

Log retention and rotation for `failure_log_path` and `event_log_path` are the operator responsibility (for example via `logrotate` or a platform logging agent). The system MUST tolerate the log files being rotated, truncated, or replaced between writes.
