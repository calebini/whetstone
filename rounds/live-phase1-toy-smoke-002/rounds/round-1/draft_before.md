# Toy Notification Spec

## Purpose

Send a notification when a watched file changes.

## Roles

- Watcher: observes file changes.
- Sender: sends notifications.
- Operator: configures the watched file and destination.

## Behavior

The system checks the file periodically.

If the file changed, the system sends a notification.

## Configuration

```yaml
watch_path: ./input.txt
destination: ops@example.com
poll_interval_seconds: 60
```

## Failure Handling

If sending fails, the system records the failure.
