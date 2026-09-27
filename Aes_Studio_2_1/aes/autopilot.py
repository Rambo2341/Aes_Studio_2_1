from __future__ import annotations
"""Aes Autopilot: works through a queue of goals while the owner is away.

Queue goals from chat (goal_add tool), from the CLI (python main.py --goal "..."),
then run `python main.py --autopilot` (or run_autopilot.bat) before sleeping.
Each goal gets its own conversation. A morning report is written to <data>/reports/.

Emergency stop: create a file named STOP in the Aes data folder, or press Ctrl+C.
"""
import time
from pathlib import Path
from .paths import DATA, REPORTS

STOP_FILE = DATA / 'STOP'


class Autopilot:
    def __init__(self, db, agent, log=print):
        self.db = db; self.agent = agent; self.log = log

    def stop_requested(self):
        return STOP_FILE.exists() or self.db.setting('autopilot_stop', '0') == '1'

    def _rounds(self):
        try: return max(1, min(50, int(self.db.setting('autopilot_rounds', '6'))))
        except Exception: return 6

    def run_goal(self, goal, model_name):
        gid = goal['id']
        self.db.update_goal(gid, status='running')
        if goal['kind'] == 'learn':
            result = self.agent.learn(model_name, goal['title'] + (' ' + goal['detail'] if goal['detail'] else ''), 2)
            status = 'failed' if result.startswith('ERROR') or result.startswith('Could not') else 'done'
            self.db.update_goal(gid, status=status, result=result[:20000])
            return status, result
        cid = goal['conversation_id'] or self.db.new_conversation(f"Autopilot: {goal['title'][:50]}", goal['project_id'], model_name, 'agent')
        self.db.update_goal(gid, conversation_id=cid)
        prompt = (f"AUTOPILOT GOAL #{gid}: {goal['title']}\n\n{goal['detail'] or ''}\n\n"
                  "The owner is away. Work autonomously within your permission mode. First state the outcome and a "
                  "Definition of Done, then execute, test and verify. If something needs the owner, finish everything "
                  "else and list the blocker clearly.")
        answer = ''; status = 'incomplete'
        for rnd in range(self._rounds()):
            if self.stop_requested():
                status = 'stopped'; break
            answer, _, _ = self.agent.run(cid, model_name, prompt, 'agent', goal['project_id'])
            verdict = self._judge(model_name, goal, answer)
            self.log(f'  goal #{gid} round {rnd+1}: {verdict[:120]}')
            if verdict.upper().startswith('DONE'):
                status = 'done'; break
            if verdict.upper().startswith('BLOCKED'):
                status = 'blocked'; answer += '\n\n' + verdict; break
            prompt = 'Continue the autopilot goal. Next step according to your own review:\n' + verdict
        self.db.update_goal(gid, status=status, result=answer[:20000])
        return status, answer

    def _judge(self, model_name, goal, answer):
        model = self.db.model(model_name)
        q = (f"Goal: {goal['title']}\n{goal['detail'] or ''}\n\nLatest agent report:\n{answer[-12000:]}\n\n"
             "Judge strictly from evidence in the report (tool results, tests). Reply with exactly one line starting with:\n"
             "DONE: <why the definition of done is met>\nCONTINUE: <the single most useful next step>\n"
             "BLOCKED: <what only the owner can provide>")
        try:
            return self.agent._complete(model, [{'role': 'system', 'content': 'You are a strict reviewer of agent work.'},
                                                {'role': 'user', 'content': q}]).strip() or 'CONTINUE: (empty verdict)'
        except Exception as e:
            return f'BLOCKED: model error while reviewing: {e}'

    def run_all(self, model_name, max_goals=50):
        started = time.time(); done = []
        if STOP_FILE.exists():
            self.log(f'Remove {STOP_FILE} to allow Autopilot to run.'); return None
        for _ in range(max_goals):
            if self.stop_requested(): break
            queue = self.db.goals('queued')
            if not queue: break
            goal = queue[0]
            self.log(f'Autopilot -> goal #{goal["id"]} [{goal["kind"]}] {goal["title"]}')
            try:
                status, result = self.run_goal(goal, model_name)
            except KeyboardInterrupt:
                self.db.update_goal(goal['id'], status='queued'); raise
            except Exception as e:
                status, result = 'failed', f'ERROR: {e}'
                self.db.update_goal(goal['id'], status=status, result=result)
            done.append((goal, status, result))
        return self.write_report(done, started, model_name)

    def write_report(self, done, started, model_name):
        stamp = time.strftime('%Y-%m-%d_%H%M')
        p = Path(REPORTS) / f'autopilot_{stamp}.md'
        lines = [f'# Aes Autopilot report — {time.strftime("%Y-%m-%d %H:%M")}', '',
                 f'Brain: {model_name}  ·  Duration: {int((time.time()-started)/60)} min  ·  Goals processed: {len(done)}', '']
        icon = {'done': '✅', 'blocked': '⛔', 'failed': '❌', 'stopped': '⏹', 'incomplete': '🟡'}
        for g, status, result in done:
            lines += [f'## {icon.get(status, "•")} #{g["id"]} {g["title"]} — {status}', '', result.strip()[:6000] or '(no output)', '']
        waiting = self.db.goals('queued')
        if waiting:
            lines += ['## Still queued', ''] + [f'- #{g["id"]} {g["title"]}' for g in waiting]
        p.write_text('\n'.join(lines), encoding='utf-8')
        self.db.log('autopilot', f'{len(done)} goals -> {p}', True)
        return p
