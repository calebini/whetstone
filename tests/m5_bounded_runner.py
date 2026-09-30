"""Run one M5 test worker with a CPU duty limit, deadline and chat heartbeat.

Developer acceptance harness only. No Whetstone capability or authority changes.
Touch OUTPUT/heartbeat while actively supervising. A stale heartbeat ends the
whole worker process group, including a worker paused by the duty limiter.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def run(command, output, *, lock_path, wall_seconds=300, lease_seconds=90, duty=0.5):
    if not command or not 0 < duty <= 1 or wall_seconds <= 0 or lease_seconds <= 0:
        raise ValueError('command, positive deadlines and 0 < duty <= 1 required')
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    lock_path = Path(lock_path); lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path.open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError('another bounded M5 worker is active') from None
    lease = output / 'heartbeat'; lease.touch()
    started = time.monotonic(); worker = None; outcome = 'interrupted'; code = 130
    old_handlers = {}
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    def group(sig):
        if worker is not None:
            try: os.killpg(worker.pid, sig)
            except ProcessLookupError: pass
            except PermissionError:
                # macOS sandbox can report EPERM for an already exited group.
                # Never suppress refusal to signal a still-running leader.
                if worker.poll() is None: raise
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            old_handlers[sig] = signal.signal(sig, interrupt)
        with (output / 'tests.log').open('wb') as log:
            worker = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            status = dict(pid=worker.pid, command=command, duty=duty, wall_seconds=wall_seconds,
                          lease_seconds=lease_seconds, outcome='running')
            (output / 'status.json').write_text(json.dumps(status, indent=2)+'\n')
            while True:
                if worker.poll() is not None:
                    code = worker.returncode; outcome = 'completed'; break
                if time.monotonic()-started >= wall_seconds:
                    outcome = 'wall_deadline'; code = 124; break
                if time.time()-lease.stat().st_mtime >= lease_seconds:
                    outcome = 'heartbeat_expired'; code = 124; break
                group(signal.SIGCONT)
                time.sleep(0.2*duty)
                if duty < 1:
                    group(signal.SIGSTOP)
                    time.sleep(0.2*(1-duty))
    except KeyboardInterrupt:
        pass
    finally:
        # Group cleanup also handles descendants left after the leader exits.
        if worker is not None:
            group(signal.SIGCONT); group(signal.SIGTERM)
            try: worker.wait(timeout=2)
            except subprocess.TimeoutExpired:
                group(signal.SIGKILL); worker.wait()
            group(signal.SIGKILL)
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)
        (output/'status.json').write_text(json.dumps(dict(
            command=command, outcome=outcome, exit_code=code, duty=duty,
            wall_seconds=wall_seconds, lease_seconds=lease_seconds,
            elapsed_seconds=time.monotonic()-started), indent=2)+'\n')
        lock.close()
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wall-seconds', type=float, default=300)
    parser.add_argument('--lease-seconds', type=float, default=90)
    parser.add_argument('--duty', type=float, default=0.5)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    lock_path = Path(__file__).resolve().parents[1]/'rounds/.m5-test-owner.lock'
    return run(command, args.output, lock_path=lock_path, wall_seconds=args.wall_seconds,
               lease_seconds=args.lease_seconds, duty=args.duty)


if __name__ == '__main__':
    raise SystemExit(main())
