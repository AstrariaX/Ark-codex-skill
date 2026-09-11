"""Read-only incremental event monitoring; disk I/O runs outside Qt's UI thread."""
import datetime
import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def timestamp(value):
    if isinstance(value, (int, float)):
        return value / 1000 if value > 100_000_000_000 else value
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except ValueError:
            pass
    return None

def clean(text):
    return ' '.join(text.split())[:160]

class LogMonitor:
    def __init__(self, root=None, thread_id=None):
        self.root = Path(root or Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'sessions')
        self.thread_id = thread_id
        self.path = None
        self.next_scan = 0
        self.reset()

    def reset(self):
        self.state = dict(active=False, phase='unknown', task=None, model=None,
                          progress=None, tokens=None, started_at=None, finished_at=None,
                          turn_id=None, event_key=None)
        self.offset = 0
        self.pending = b''

    def consume(self, obj):
        p = obj.get('payload') or {}
        if not isinstance(p, dict):
            return
        kind, event = obj.get('type'), p.get('type')
        stamp = timestamp(obj.get('timestamp'))
        if kind == 'event_msg':
            if event == 'task_started':
                self.state.update(active=True, phase='running', turn_id=p.get('turn_id'),
                                  started_at=timestamp(p.get('started_at')) or stamp,
                                  progress=None, task=None,
                                  event_key=(p.get('turn_id'), event, stamp))
            elif event in ('task_complete', 'turn_aborted', 'task_failed'):
                if p.get('turn_id') and self.state['turn_id'] and p['turn_id'] != self.state['turn_id']:
                    return
                phase = {'task_complete':'completed', 'turn_aborted':'interrupted', 'task_failed':'failed'}[event]
                self.state.update(active=False, phase=phase,
                                  finished_at=timestamp(p.get('completed_at')) or stamp,
                                  event_key=(p.get('turn_id'), event, stamp))
                if isinstance(p.get('last_agent_message'), str):
                    self.state['progress'] = clean(p['last_agent_message'])
            elif event == 'user_message' and isinstance(p.get('message'), str):
                self.set_task(p['message'])
            elif event == 'agent_message' and p.get('phase') == 'commentary':
                self.state['progress'] = clean(p.get('message', ''))
            elif event == 'token_count':
                self.state['tokens'] = ((p.get('info') or {}).get('total_token_usage') or {}).get('total_tokens')
            elif event == 'thread_settings_applied':
                self.state['model'] = (p.get('thread_settings') or {}).get('model', self.state['model'])
        if kind == 'turn_context' and p.get('model'):
            self.state['model'] = p['model']
        if kind == 'response_item' and event == 'message':
            content = p.get('content', [])
            text = content if isinstance(content,str) else ''.join(x.get('text','') for x in content if isinstance(x,dict) and isinstance(x.get('text'),str))
            if p.get('role') == 'user':
                self.set_task(text)
            elif p.get('role') == 'assistant' and p.get('phase') == 'commentary':
                self.state['progress'] = clean(text)

    def set_task(self, text):
        if text and not any(marker in text for marker in ('<environment_context>', '<permissions instructions>', '<turn_aborted>')):
            self.state['task'] = clean(text.split('My request for Codex:')[-1])

    def poll(self):
        try:
            if self.path is None and time.monotonic() >= self.next_scan:
                self.next_scan = time.monotonic() + 3
                files = [p for p in self.root.rglob('rollout-*.jsonl')
                         if not self.thread_id or p.name.endswith(self.thread_id + '.jsonl')]
                if files:
                    self.path = max(files, key=lambda p:p.stat().st_mtime)
            if self.path is not None:
                size = self.path.stat().st_size
                if size < self.offset:
                    self.reset()
                if size > self.offset:
                    with self.path.open('rb') as f:
                        f.seek(self.offset)
                        data = f.read(4*1024*1024)
                        self.offset = f.tell()
                    lines = (self.pending + data).split(b'\n')
                    self.pending = lines.pop()
                    for line in lines:
                        try:
                            obj = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        if isinstance(obj, dict):
                            self.consume(obj)
                self.state['error'] = None
        except OSError as exc:
            self.path = None
            self.reset()
            self.state['error'] = str(exc)
        result = dict(self.state)
        start, end = result['started_at'], result['finished_at']
        result['elapsed'] = max(0,int(time.time()-start)) if result['active'] and start else None
        result['last_finished'] = datetime.datetime.fromtimestamp(end).strftime('%H:%M:%S') if end else None
        # Do not animate historical transitions while replaying a large log.
        if self.path and self.offset < size:
            result.update(active=False, phase='unknown', event_key=None)
        return result

class GlobalMonitor:
    """Aggregate independent incremental readers; never finish while any is active."""
    def __init__(self, root=None):
        self.thread_id = None
        self.root = Path(root or Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'sessions')
        self.readers = {}
        self.next_scan = 0

    def poll(self):
        try:
            if time.monotonic() >= self.next_scan:
                paths = set(self.root.rglob('rollout-*.jsonl'))
                self.next_scan = time.monotonic() + 1.0
                for path in paths:
                    if path not in self.readers:
                        reader = LogMonitor(self.root)
                        reader.path = path
                        self.readers[path] = reader
                for path in set(self.readers) - paths:
                    del self.readers[path]
            states = []
            loading = False
            for path, reader in self.readers.items():
                # Keep each reader attached to exactly one task file.
                reader.path = path
                state = reader.poll()
                # Catch up large historical logs in the worker, not over dozens
                # of UI timer ticks. Work remains bounded to 32 MiB per file.
                for _ in range(7):
                    if state.get('error') or reader.offset >= path.stat().st_size:
                        break
                    state = reader.poll()
                loading |= bool(state.get('error')) or reader.offset < path.stat().st_size
                states.append((str(path), state))
            if loading:
                return dict(active=False, phase='unknown', event_key=None)
            active = [(path, s) for path, s in states if s.get('active')]
            if active:
                result = dict(max(active, key=lambda item: item[1].get('started_at') or 0)[1])
                result.update(active_count=len(active), event_key=('global-running', tuple(sorted(
                    (path, str(s.get('event_key'))) for path, s in active))))
                return result
            terminal = [(path, s) for path, s in states if s.get('finished_at') is not None]
            if terminal:
                path, state = max(terminal, key=lambda item: item[1]['finished_at'])
                result = dict(state)
                result.update(active_count=0, event_key=('global-terminal', path, state.get('event_key')))
                return result
            return dict(active=False, phase='unknown', event_key=None, active_count=0)
        except OSError as exc:
            return dict(active=False, phase='unknown', event_key=None, error=str(exc))


_monitor = None
_future = None
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pet-log-reader')
_latest = dict(active=False, phase='unknown')

def get_codex_status(thread_id=None):
    global _monitor, _future, _latest
    if _monitor is not None and _monitor.thread_id != thread_id:
        if _future is not None and not _future.done():
            return dict(active=False, phase='unknown')
        _future = None
        _monitor = None
        _latest = dict(active=False, phase='unknown')
    if _monitor is None:
        _monitor = GlobalMonitor() if thread_id is None else LogMonitor(thread_id=thread_id)
    if _future is not None and _future.done():
        try:
            _latest = _future.result()
        except Exception as exc:
            _latest = dict(active=False, phase='unknown', error=str(exc))
        _future = None
    if _future is None:
        _future = _executor.submit(_monitor.poll)
    return dict(_latest)
