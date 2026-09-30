"""The M5 supervisor must reclaim unattended workers and serialize starts."""
import fcntl
import json
from pathlib import Path
import sys
import time
from tempfile import TemporaryDirectory
import unittest
from m5_bounded_runner import run


class BoundedRunnerTests(unittest.TestCase):
    def test_completed_worker_and_busy_owner(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);lock=root/'owner'
            command=[sys.executable,'-c','print("complete")']
            self.assertEqual(run(command,root/'done',lock_path=lock),0)
            self.assertIn('complete',(root/'done/tests.log').read_text())
            with lock.open('a') as held:
                fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError,'active'):
                    run(command,root/'busy',lock_path=lock)
            self.assertFalse((root/'busy/tests.log').exists())

    def test_lease_and_deadline_reclaim_paused_worker(self):
        for reason, options in [('heartbeat_expired',dict(lease_seconds=0.25,wall_seconds=10)),
                                ('wall_deadline',dict(lease_seconds=10,wall_seconds=0.25))]:
            with self.subTest(reason=reason),TemporaryDirectory() as directory:
                root=Path(directory)
                code=run([sys.executable,'-c','import time;time.sleep(60)'],root/'run',
                         lock_path=root/'owner',duty=0.25,**options)
                self.assertEqual(code,124)
                state=json.loads((root/'run/status.json').read_text())
                self.assertEqual(state['outcome'],reason)
                self.assertLess(state['elapsed_seconds'],5)

    def test_expired_lease_terminates_worker_descendants(self):
        with TemporaryDirectory() as directory:
            root=Path(directory); marker=root/'survived'
            child='import time; from pathlib import Path; time.sleep(1); Path('+repr(str(marker))+').write_text("alive")'
            parent='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'+repr(child)+']); time.sleep(60)'
            self.assertEqual(run([sys.executable,'-c',parent],root/'run',lock_path=root/'owner',
                                 lease_seconds=0.25,wall_seconds=10,duty=0.5),124)
            time.sleep(1)
            self.assertFalse(marker.exists())
