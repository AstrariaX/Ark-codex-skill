import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1] / 'ark-codex-skill/assets/deskpet-app'
sys.path.insert(0, str(APP))
from monitor_events import GlobalMonitor
from single_instance import InstanceLock


def event(kind, turn, stamp):
    return (json.dumps(dict(type='event_msg', timestamp=stamp,
                           payload=dict(type=kind, turn_id=turn))) + '\n').encode()


class GlobalTests(unittest.TestCase):
    def test_concurrent_tasks_discovery_and_incremental_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / 'rollout-a.jsonl'
            first.write_bytes(event('task_started', 'a', 1))
            monitor = GlobalMonitor(root)
            self.assertEqual(monitor.poll()['active_count'], 1)
            offset = monitor.readers[first].offset
            self.assertTrue(monitor.poll()['active'])
            self.assertEqual(monitor.readers[first].offset, offset)
            second = root / 'rollout-b.jsonl'
            second.write_bytes(event('task_started', 'b', 2))
            monitor.next_scan = 0
            self.assertEqual(monitor.poll()['active_count'], 2)
            with first.open('ab') as f:
                f.write(event('task_complete', 'a', 3))
            self.assertEqual(monitor.poll()['active_count'], 1)
            with second.open('ab') as f:
                f.write(event('task_complete', 'wrong-turn', 4))
            self.assertTrue(monitor.poll()['active'])
            ending = event('task_complete', 'b', 5)
            with second.open('ab') as f:
                f.write(ending[:15])
            self.assertTrue(monitor.poll()['active'])
            with second.open('ab') as f:
                f.write(ending[15:])
            completed = monitor.poll()
            self.assertEqual(completed['phase'], 'completed')
            self.assertFalse(completed['active'])
            self.assertEqual(completed['event_key'], monitor.poll()['event_key'])
            # An existing old-date file resumes, not just newly created logs.
            with first.open('ab') as f:
                f.write(event('task_started', 'c', 6))
            self.assertTrue(monitor.poll()['active'])
            with first.open('ab') as f:
                f.write(event('turn_aborted', 'c', 7))
            self.assertEqual(monitor.poll()['phase'], 'interrupted')
            # Restart reconstructs the same aggregate terminal state.
            self.assertEqual(GlobalMonitor(root).poll()['phase'], 'interrupted')
            second.write_bytes(event('task_started', 'd', 8))
            self.assertTrue(monitor.poll()['active'])

    def test_duplicate_process_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = InstanceLock(directory)
            self.assertTrue(owner.acquire())
            child = ('from single_instance import InstanceLock; import sys; '
                     'lock=InstanceLock(sys.argv[1]); '
                     'print(lock.acquire()); lock.close()')
            def probe():
                return subprocess.check_output([sys.executable, '-B', '-c', child, directory],
                                               cwd=APP, text=True).strip()
            try:
                self.assertEqual(probe(), 'False')
            finally:
                owner.close()
            self.assertEqual(probe(), 'True')
            # Child exits and releases the OS handle: no stale PID/lock recovery needed.
            self.assertTrue(owner.acquire())
            owner.close()


if __name__ == '__main__':
    unittest.main()
