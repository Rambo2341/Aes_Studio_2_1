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
        if 'strict reviewer' in system:
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
            self.assertIn('aes-identity-version: 2.2', (IDENTITY_DATA / n).read_text(encoding='utf-8'))

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
