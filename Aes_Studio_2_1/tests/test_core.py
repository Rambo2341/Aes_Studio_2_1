"""Headless tests for the Aes core (no GUI, no real model needed).

Run:  python -m unittest discover -s tests -v
"""
import json, os, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix='aes_test_')
os.environ['AES_DATA_DIR'] = _TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aes.paths import DATA, IDENTITY_DATA  # noqa: E402
from aes.db import Database  # noqa: E402
from aes.model_runtime import RuntimeManager  # noqa: E402
from aes.security import PermissionManager  # noqa: E402
from aes.tools import ToolRegistry, html_to_text  # noqa: E402
from aes.agent import AgentEngine  # noqa: E402
from aes.autopilot import Autopilot  # noqa: E402


class FakeLLM(BaseHTTPRequestHandler):
    """A tiny OpenAI-compatible server that scripts tool use."""
    requests = []

    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        FakeLLM.requests.append(body)
        msgs = body['messages']; last = msgs[-1]['content']
        last = last if isinstance(last, str) else ' '.join(p.get('text', '') for p in last)
        system = msgs[0]['content'] if msgs and msgs[0]['role'] == 'system' else ''
        if 'SLEEP LOOP' in json.dumps(msgs):
            reply = '<tool_call>{"name":"run_python","arguments":{"code":"import time; time.sleep(20)"}}</tool_call>'
        elif 'syllabus' in last:
            reply = '["Blender interface", "Blender modifiers"]'
        elif 'follow-up lessons' in last:
            reply = '["Blender modifiers", "Blender geometry nodes"]'
        elif 'strict reviewer' in system:
            reply = 'DONE: file exists per tool result'
        elif 'Study topic' in last:
            reply = '# Notes\nPythagoras: a^2+b^2=c^2 [1]'
        elif 'Step budget reached' in last:
            reply = 'Status: partial work, budget reached.'
        elif 'LOOP FOREVER' in json.dumps(msgs):
            reply = '<tool_call>{"name":"list_files","arguments":{}}</tool_call>'
        elif '<tool_result' in last:
            reply = 'Finished. Evidence: ' + last[-80:]
        elif 'write hello' in last.lower():
            reply = '<tool_call>{"name":"write_file","arguments":{"path":"hello.txt","content":"hi"}}</tool_call>'
        else:
            reply = 'Hello, I am Aes.'
        data = json.dumps({'choices': [{'message': {'role': 'assistant', 'content': reply}}]}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)


class AesCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(('127.0.0.1', 0), FakeLLM)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.db = Database(Path(_TMP) / 'test.db')
        cls.db.save_model('Fake', 'openai_compat', 'fake-model', 8192, 0, 0.2, 512, 'You are Aes.', 1,
                          f'http://127.0.0.1:{cls.srv.server_address[1]}/v1', '')
        cls.db.set_setting('permission_mode', 'full')
        cls.runtimes = RuntimeManager()
        cls.tools = ToolRegistry(Path(_TMP) / 'ws', cls.db, PermissionManager(cls.db))
        cls.agent = AgentEngine(cls.db, cls.runtimes, cls.tools)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.db.close()

    def test_data_dir_and_identity(self):
        self.assertEqual(str(DATA), _TMP)
        for n in ('SOUL.md', 'IDENTITY.md', 'USER.md'):
            self.assertIn('aes-identity-version: 2.3', (IDENTITY_DATA / n).read_text(encoding='utf-8'))

    def test_seeded_profiles_and_token(self):
        names = {r['name'] for r in self.db.models()}
        self.assertTrue({'Aes 2.2 Claude', 'Aes 2.2 Ollama', 'Aes 2.2 DeepSeek'} <= names)
        self.assertNotEqual(self.db.setting('hub_token'), 'change-me')
        self.assertGreaterEqual(len(self.db.setting('hub_token')), 30)

    def test_agent_tool_loop_writes_file(self):
        cid = self.db.new_conversation('t')
        ans, mid, traces = self.agent.run(cid, 'Fake', 'please write hello')
        self.assertEqual(traces[0]['tool'], 'write_file')
        self.assertEqual((self.tools.workspace / 'hello.txt').read_text(), 'hi')
        self.assertTrue(ans.startswith('Finished.'))
        sysmsg = FakeLLM.requests[-1]['messages'][0]['content']
        self.assertIn('AES SELF MODEL', sysmsg)
        self.assertIn('Aes — SOUL', sysmsg)

    def test_step_budget_gives_status_not_tool_call(self):
        self.db.set_setting('agent_max_steps', '3')
        try:
            cid = self.db.new_conversation('t')
            ans, _, traces = self.agent.run(cid, 'Fake', 'LOOP FOREVER')
        finally:
            self.db.set_setting('agent_max_steps', '30')
        self.assertEqual(len(traces), 3)
        self.assertNotIn('<tool_call>', ans)
        self.assertIn('budget', ans)

    def test_ask_mode_without_ui_denies_writes(self):
        self.db.set_setting('permission_mode', 'ask')
        try:
            out = self.agent._call_tool('write_file', {'path': 'x.txt', 'content': 'no'}, None, 'Fake', None, 0)
        finally:
            self.db.set_setting('permission_mode', 'full')
        self.assertIn('ERROR', out)
        self.assertFalse((self.tools.workspace / 'x.txt').exists())

    def test_destructive_command_blocked(self):
        with self.assertRaises(Exception):
            self.tools.call('run_command', {'cmd': 'format c: /q', 'shell': 'true'})

    def test_run_python_and_recall(self):
        out = self.tools.call('run_python', {'code': 'print(2**10)'})
        self.assertIn('1024', out)
        self.tools.call('remember', {'text': 'Owner prefers Luau strict mode', 'tags': 'roblox'})
        self.assertIn('Luau strict', self.tools.call('recall', {'query': 'luau strict roblox'}))

    def test_learn_topic_stores_knowledge(self):
        self.tools._web_search = lambda q, max_results=8: '1. Pythagoras\n   https://example.org/p'
        self.tools._fetch_url = lambda u, max_chars=12000: 'a^2+b^2=c^2 explained'
        out = self.agent.learn('Fake', 'Pythagorean theorem')
        self.assertIn('Learned', out)
        self.assertIn('Pythagoras', self.tools.call('recall', {'query': 'Pythagorean theorem notes'}))

    def test_autopilot_goal_and_report(self):
        gid = self.db.add_goal('write hello file', 'hello.txt contains hi')
        report = Autopilot(self.db, self.agent, log=lambda m: None).run_all('Fake')
        self.assertEqual(self.db.one('SELECT status FROM goals WHERE id=?', (gid,))['status'], 'done')
        self.assertIn('write hello file', Path(report).read_text(encoding='utf-8'))

    def test_image_marker_becomes_vision_input(self):
        from PIL import Image
        img = Path(_TMP) / 'shot.png'; Image.new('RGB', (4, 4)).save(img)
        from aes.model_runtime import OpenAICompatRuntime, AnthropicRuntime
        conv = OpenAICompatRuntime('http://x/v1', '')._convert([{'role': 'user', 'content': f'look [[aes-image:{img}]]'}])
        self.assertEqual(conv[0]['content'][1]['type'], 'image_url')
        rt = AnthropicRuntime.__new__(AnthropicRuntime)
        system, msgs = rt._convert([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': f'[[aes-image:{img}]] what?'}])
        self.assertEqual(system, 'S'); self.assertEqual(msgs[0]['content'][0]['type'], 'image')

    def test_read_document_and_library(self):
        lib = Path(_TMP) / 'magazines'; lib.mkdir(exist_ok=True)
        (lib / 'issue1.md').write_text('Quaternions avoid gimbal lock in 3D rotation.', encoding='utf-8')
        (lib / 'issue2.txt').write_text('Luau generics use angle brackets.', encoding='utf-8')
        out = self.tools.call('read_document', {'path': str(lib / 'issue1.md'), 'max_chars': 10})
        self.assertIn('Quaternion', out); self.assertIn('start_char=10', out)
        self.assertIn('Imported 2', self.tools.call('library_import', {'folder': str(lib)}))
        self.assertIn('Imported 0', self.tools.call('library_import', {'folder': str(lib)}))  # no duplicates
        self.assertIn('gimbal', self.tools.call('recall', {'query': 'quaternions gimbal'}))

    def test_video_helpers_and_learning(self):
        from aes.tools import youtube_id, vtt_to_text
        self.assertEqual(youtube_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1'), 'dQw4w9WgXcQ')
        self.assertEqual(youtube_id('https://youtu.be/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        vtt = 'WEBVTT\n\n00:00.000 --> 00:01.000\nhello <c>world</c>\n\n00:01.000 --> 00:02.000\nhello world\nnext line'
        self.assertEqual(vtt_to_text(vtt), 'hello world next line')
        self.tools._video_transcript = lambda src, max_chars=60000: 'recursion means a function calls itself'
        out = self.agent.learn_from_video('Fake', 'https://youtu.be/dQw4w9WgXcQ', 'recursion')
        self.assertIn('Learned from video', out)

    def test_curriculum_queue(self):
        from aes.curriculum import queue, load
        self.assertGreater(len(load()['units']), 30)
        n = queue(self.db, 'roblox', 'high-school')
        self.assertGreater(n, 0)
        self.assertEqual(queue(self.db, 'roblox', 'high-school'), 0)  # idempotent
        titles = [g['title'] for g in self.db.goals('queued')]
        self.assertTrue(any('Study:' in t for t in titles) and any('Practice:' in t for t in titles))
        self.db.execute("DELETE FROM goals WHERE title LIKE '[roblox-%'")

    def test_drill_grading(self):
        from aes.drills import math_matches, run_kata, KATAS
        self.assertTrue(math_matches('work\nAnswer: (x=3, y=-2)', '3,-2'))
        self.assertTrue(math_matches('Answer: 0.5', '1/2'))
        self.assertFalse(math_matches('Answer: 7', '8'))
        good = 'def gcd(a, b):\n    while b: a, b = b, a % b\n    return a'
        self.assertTrue(run_kata(good, 'gcd', KATAS[3][2]))
        self.assertFalse(run_kata('def gcd(a, b): return 1', 'gcd', KATAS[3][2]))

    def test_queue_next_progresses_evenly(self):
        from aes.curriculum import queue_next
        self.assertEqual(queue_next(self.db, 3), 6)
        first = [g['title'] for g in self.db.goals('queued') if 'Study:' in g['title']]
        self.assertEqual(len(first), 3)
        self.assertEqual(len({t.split('-')[0] for t in first}), 3)   # three different tracks
        queue_next(self.db, 3)
        self.assertEqual(len({g['title'] for g in self.db.goals('queued') if g['title'].startswith('[')}), 12)  # no repeats
        self.db.execute("DELETE FROM goals WHERE title LIKE '[%'")

    def test_daily_cycle_report(self):
        from aes.daily import DailyTrainer
        self.db.set_setting('daily_math_drills', '4'); self.db.set_setting('daily_code_drills', '2')
        before = len(self.db.training_examples())
        report = DailyTrainer(self.db, self.agent, log=lambda m: None).run('Fake', school=False, hours=0)
        text = Path(report).read_text(encoding='utf-8')
        self.assertIn('Maths/science drills: 0/4', text)   # the fake model answers wrong ...
        self.assertIn('LoRA training is off', text)
        self.assertGreaterEqual(len(self.db.training_examples()) - before, 4)  # ... so it gets correction examples
        self.assertEqual(len(json.loads(self.db.setting('daily_history'))), 1)

    def test_research_mode_expands_and_archives(self):
        from aes.research import ResearchMode
        self.tools._web_search = lambda q, max_results=8: f'1. {q}\n   https://example.org/{abs(hash(q))}'
        self.tools._fetch_url = lambda u, max_chars=12000: 'Blender tutorial text'
        self.tools._video_search = lambda q, n=3: '(no videos found)'
        report = ResearchMode(self.db, self.agent, log=lambda m: None).run('Fake', 'Master Blender', hours=1, max_topics=3)
        text = Path(report).read_text(encoding='utf-8')
        self.assertIn('Lessons studied: 3/3', text)
        self.assertIn('Blender geometry nodes', text)          # discovered by itself
        self.assertEqual(text.count('Blender modifiers'), 1)   # no duplicate lessons
        self.assertTrue(list((DATA / 'library' / 'raw').rglob('*.txt')))  # raw sources archived

    def test_stop_cancels_running_task_and_kills_process(self):
        import time as _t
        cid = self.db.new_conversation('t'); out = {}
        th = threading.Thread(target=lambda: out.update(r=self.agent.run(cid, 'Fake', 'SLEEP LOOP')))
        t0 = _t.time(); th.start(); _t.sleep(1.5); self.agent.cancel(); th.join(15)
        self.assertFalse(th.is_alive())
        self.assertLess(_t.time() - t0, 10)               # the 20 s process was killed
        self.assertIn('Stopped by owner', out['r'][0])
        self.agent.cancel_event.clear()

    def test_streaming_tokens_reach_listeners(self):
        events = []
        self.agent.listeners.append(events.append)
        try:
            cid = self.db.new_conversation('t')
            ans, _, _ = self.agent.run(cid, 'Fake', 'hello there')
        finally:
            self.agent.listeners.remove(events.append)
        types = [e['type'] for e in events]
        self.assertIn('run_start', types); self.assertIn('run_end', types)
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'token'), ans)

    def test_hardware_recommendation_and_cloud_flag(self):
        from aes.hardware import recommend, is_cloud
        self.assertEqual(recommend(8.0)['brain'], 'qwen2.5vl:7b')        # RTX 3070
        self.assertFalse(is_cloud(self.db.model('Aes Local')))
        self.assertTrue(is_cloud(self.db.model('Aes 2.2 Claude')))
        self.assertEqual(self.db.setting('default_model'), 'Aes Local')   # local-first default

    def test_qt_interface_smoke(self):
        try:
            os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
            from PySide6.QtWidgets import QApplication
            from aes import qt_ui
        except Exception as e:
            self.skipTest(f'PySide6 not available: {e}')
        import time as _t
        app = QApplication.instance() or QApplication([])
        w = qt_ui.AesWindow(None, core=(self.db, self.runtimes, self.tools, self.agent))
        i = w.model_box.findData('Fake'); w.model_box.setCurrentIndex(i)
        w.prompt.setPlainText('hello from the UI'); w.send()
        deadline = _t.time() + 15
        while w.busy and _t.time() < deadline:
            app.processEvents(); _t.sleep(0.05)
        app.processEvents()
        self.assertIsNone(w.busy)
        texts = [b.body.text() for b in w.view.inner.findChildren(qt_ui.Bubble)]
        self.assertIn('Hello, I am Aes.', texts)
        for page in w.PAGES: w.show_page(page); app.processEvents()
        self.agent.listeners.clear(); w.deleteLater()

    def test_html_to_text(self):
        self.assertEqual(html_to_text('<html><script>x()</script><p>Hi &amp; bye</p></html>'), 'Hi & bye')

    def test_hub_auth_and_goals(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest('fastapi/httpx not installed')
        from aes.hub import AesHub
        c = TestClient(AesHub(self.db, self.runtimes, self.agent).app)
        tok = {'Authorization': 'Bearer ' + self.db.setting('hub_token')}
        self.assertEqual(c.post('/v1/goals', json={'title': 'x'}).status_code, 401)
        self.assertEqual(c.post('/v1/goals', json={'title': 'remote goal'}, headers=tok).status_code, 200)
        self.assertEqual(c.post('/v1/agent', json={'message': 'hi'}, headers=tok).status_code, 403)
        self.db.set_setting('hub_agent_enabled', '1')
        r = c.post('/v1/agent', json={'message': 'hi', 'model': 'Fake'}, headers=tok)
        self.db.set_setting('hub_agent_enabled', '0')
        self.assertEqual(r.json()['reply'], 'Hello, I am Aes.')


if __name__ == '__main__':
    unittest.main()
