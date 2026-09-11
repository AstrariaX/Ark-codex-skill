import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'ark-codex-skill' / 'assets' / 'deskpet-app'
sys.path.insert(0, str(APP))
from monitor_events import LogMonitor, timestamp

def event(name, turn='one'):
    return json.dumps({'type':'event_msg','timestamp':'2026-09-08T12:00:00Z',
                       'payload':{'type':name,'turn_id':turn}}).encode()+b'\n'

class MonitorTests(unittest.TestCase):
    def test_incremental_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'rollout-test-abc.jsonl'
            path.write_bytes(event('task_started'))
            m=LogMonitor(d,'abc')
            self.assertTrue(m.poll()['active'])
            offset=m.offset
            os.utime(path,(1,1))
            self.assertTrue(m.poll()['active'])
            self.assertEqual(offset,m.offset)
            data=event('task_complete')
            with path.open('ab') as f: f.write(data[:20])
            self.assertTrue(m.poll()['active'])
            with path.open('ab') as f: f.write(data[20:])
            self.assertEqual(m.poll()['phase'],'completed')
            with path.open('ab') as f:
                f.write(b'bad-json\n'+event('task_started','two')+event('turn_aborted','one'))
            self.assertTrue(m.poll()['active'])
            with path.open('ab') as f: f.write(event('turn_aborted','two'))
            self.assertEqual(m.poll()['phase'],'interrupted')
            path.write_bytes(event('task_started','three'))
            self.assertTrue(m.poll()['active'])
            path.unlink()
            self.assertEqual(m.poll()['phase'],'unknown')

    def test_timestamp_units(self):
        self.assertEqual(timestamp(1700000000000),timestamp(1700000000))
        self.assertEqual(timestamp('2023-11-14T22:13:20Z'),1700000000)

    def test_thread_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'rollout-abc.jsonl').write_bytes(event('task_started'))
            (Path(d)/'rollout-other.jsonl').write_bytes(event('task_complete'))
            self.assertTrue(LogMonitor(d,'abc').poll()['active'])
            self.assertEqual(LogMonitor(d,'absent').poll()['phase'],'unknown')

class AssetTests(unittest.TestCase):
    def test_bundled_manifests(self):
        for pet in (APP/'pets').iterdir():
            data=json.loads((pet/'manifest.json').read_text(encoding='utf-8'))
            self.assertGreater(data['fps'],0)
            for state,info in data['states'].items():
                files=list((pet/'frames'/state).glob('frame_*.png'))
                self.assertEqual(len(files),info['count'])
                self.assertTrue(all(p.stat().st_size>0 for p in files))

@unittest.skipUnless(sys.platform=='win32','Windows UI')
class UiTests(unittest.TestCase):
    def test_actions_and_captions(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        import main
        app=QApplication.instance() or QApplication([])
        status={'active':True,'phase':'running','event_key':('one','start',1),'task':'not shown'}
        with patch.object(main,'save_settings'), patch.object(main,'load_settings',return_value=dict(main.DEFAULT_SETTINGS)), patch.object(main.codex_monitor,'get_codex_status',side_effect=lambda *a:dict(status)):
            w=main.PetWindow()
            w.status_timer.stop()
            self.assertEqual(w.state,'move')
            self.assertFalse(w.sleep_timer.isActive())
            w.frame_index=3
            w.refresh_status()
            self.assertEqual(w.frame_index,3)
            for lang,expected in [('zh','Codex 运行中'),('en','Codex Running')]:
                w.settings['subtitle_language']=lang
                w.refresh_status()
                self.assertEqual(w.status_text,expected)
            layout,_,_=w.subtitle_layout(w.width())
            self.assertEqual(layout.textOption().alignment(),Qt.AlignHCenter)
            self.assertEqual(w.grab().toImage().pixelColor(20,12).alpha(),0)
            status.update(active=False,phase='completed',event_key=('one','end',2))
            w.refresh_status()
            self.assertEqual(w.state,'interact')
            deadline = w.completed_caption_deadline
            with patch.object(main.time, 'monotonic', return_value=deadline + 0.1):
                w.refresh_status()
                self.assertEqual(w.status_text, '')
            w.move(-10000, -10000)
            w.ensure_on_screen()
            area = main.QGuiApplication.primaryScreen().availableGeometry()
            self.assertTrue(area.contains(w.geometry()))
            status.update(phase='interrupted',event_key=('one','abort',3))
            w.refresh_status()
            self.assertEqual(w.state,'sit')
            self.assertTrue(w.status_text)
            w.settings['status_actions']=False
            status.update(active=True,phase='running',event_key=('two','start',4))
            w.refresh_status()
            self.assertEqual(w.state,'sit')
            d=main.SettingsDialog(dict(main.DEFAULT_SETTINGS,subtitle_language='en',monitor_thread_id='abc'))
            self.assertEqual(d.values()['subtitle_language'],'en')
            self.assertEqual(d.values()['monitor_thread_id'],'abc')
            w.close()

if __name__=='__main__':
    unittest.main()
