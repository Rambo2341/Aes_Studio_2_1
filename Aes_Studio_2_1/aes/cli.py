from __future__ import annotations
"""Headless Aes: terminal chat, goal queue, Autopilot, self-study and the owner API server."""
import argparse, sys, time


def _console_approval(req):
    try:
        ans = input(f'\n[Aes asks] {req.tool_name} ({req.risk}): {req.summary}\nAllow? [y/N] ').strip().lower()
    except EOFError:
        return False
    return ans in ('y', 'yes', 'نعم', 'ا')


def build_core(interactive=True):
    from .paths import DB_PATH, WORKSPACE
    from .db import Database
    from .model_runtime import RuntimeManager
    from .security import PermissionManager
    from .tools import ToolRegistry
    from .agent import AgentEngine
    db = Database(DB_PATH); runtimes = RuntimeManager()
    perm = PermissionManager(db, _console_approval if interactive else None)
    tools = ToolRegistry(WORKSPACE, db, perm)
    return db, runtimes, tools, AgentEngine(db, runtimes, tools)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='aes', description='Aes Studio headless mode')
    ap.add_argument('--model', help='model profile name (default: the Studio default)')
    ap.add_argument('--chat', action='store_true', help='chat with Aes in the terminal')
    ap.add_argument('--ask', metavar='TEXT', help='one-shot request')
    ap.add_argument('--goal', metavar='TEXT', help='queue an Autopilot goal')
    ap.add_argument('--learn', metavar='TOPIC', help='queue a self-study goal')
    ap.add_argument('--detail', default='', help='definition of done / extra detail for --goal')
    ap.add_argument('--goals', action='store_true', help='list goals')
    ap.add_argument('--autopilot', action='store_true', help='work through queued goals, then write a report')
    ap.add_argument('--mode', choices=['ask', 'auto', 'full'], help='set the permission mode before running')
    ap.add_argument('--api', action='store_true', help='run the owner API server (Aes Hub) in the foreground')
    ap.add_argument('--status', action='store_true', help='print self status')
    ap.add_argument('--curriculum', nargs='?', const='all', metavar='TRACKS', help='queue the training curriculum (all, or e.g. roblox,programming)')
    ap.add_argument('--max-level', choices=['primary', 'middle', 'high-school', 'university', 'specialist'], help='limit --curriculum to this level')
    ap.add_argument('--library', metavar='FOLDER', help='import every PDF/DOCX/text file in a folder into knowledge')
    ap.add_argument('--video', metavar='URL_OR_FILE', help='queue a learn-from-video goal')
    ap.add_argument('--daily', action='store_true', help='run the daily training cycle (school, drills, exam, brain growth, report)')
    ap.add_argument('--no-school', action='store_true', help='with --daily: skip curriculum/Autopilot, only drills + exam')
    a = ap.parse_args(argv)

    db, runtimes, tools, agent = build_core(interactive=not a.autopilot and not a.api and not a.daily)
    model = a.model or db.setting('default_model', 'Aes 2.1 Local')
    if not db.model(model):
        print(f'Model profile not found: {model}. Profiles: ' + ', '.join(r['name'] for r in db.models())); return 2
    if a.mode: db.set_setting('permission_mode', a.mode)

    if a.status: print(tools.call('self_status', {}))
    if a.goal: print(f'Queued goal #{db.add_goal(a.goal, a.detail, "task")}')
    if a.learn: print(f'Queued study goal #{db.add_goal(a.learn, a.detail, "learn")}')
    if a.video: print(f'Queued video goal #{db.add_goal(a.detail or "Video lesson", a.video, "video")}')
    if a.curriculum:
        from .curriculum import queue
        print(f'Queued {queue(db, a.curriculum, a.max_level)} curriculum goal(s).')
    if a.library: print(tools.call('library_import', {'folder': a.library}))
    if a.goals:
        for g in db.goals(): print(f"#{g['id']} [{g['status']}] ({g['kind']}) {g['title']}")
    if a.ask:
        cid = db.new_conversation(a.ask[:60], None, model)
        print(agent.run(cid, model, a.ask)[0])
    if a.autopilot:
        from .autopilot import Autopilot
        print(f"Autopilot starting with brain '{model}', permission mode '{db.setting('permission_mode','ask')}'.")
        if db.setting('permission_mode', 'ask') == 'ask':
            print('Note: in Ask mode nobody is there to approve, so write/exec/computer tools will be refused. Use --mode auto or --mode full.')
        db.set_setting('autopilot_stop', '0')
        report = Autopilot(db, agent).run_all(model)
        if report: print(f'Report: {report}')
    if a.daily:
        from .daily import DailyTrainer
        db.set_setting('autopilot_stop', '0')
        print(f"Daily training with brain '{model}', permission mode '{db.setting('permission_mode','ask')}'.")
        DailyTrainer(db, agent).run(model, school=not a.no_school)
    if a.api:
        from .hub import AesHub
        hub = AesHub(db, runtimes, agent)
        port = int(db.setting('hub_port', '8765')); hub.start('127.0.0.1', port)
        print(f'Aes owner API on http://127.0.0.1:{port}  (token in Settings / hub_token). Ctrl+C to stop.')
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            hub.stop()
    if a.chat:
        cid = db.new_conversation('Terminal chat', None, model)
        print(f"Aes ({model}) — type /exit to quit, /mode ask|auto|full to change trust.")
        while True:
            try: text = input('\nأنت / you > ').strip()
            except (EOFError, KeyboardInterrupt): break
            if not text: continue
            if text in ('/exit', '/quit'): break
            if text.startswith('/mode '):
                db.set_setting('permission_mode', text.split()[1]); print('mode =', text.split()[1]); continue
            try:
                ans, _, traces = agent.run(cid, model, text)
                for t in traces: print(f"  · {t['tool']} -> {str(t['result'])[:160].replace(chr(10), ' ')}")
                print('\nAes > ' + ans)
            except Exception as e:
                print(f'ERROR: {e}')
    db.close(); return 0


if __name__ == '__main__':
    sys.exit(main())
