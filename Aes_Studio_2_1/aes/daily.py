from __future__ import annotations
"""Aes daily training: one command every night makes Aes a little better, measurably.

  1. School      - queue the next curriculum units (study + practice) and run them on Autopilot.
  2. Drills      - fresh maths/science/code problems graded by the computer (no guessing).
  3. Harvest     - verified drill answers, completed Autopilot work and owner 👍 become training data.
  4. Exam        - run the eval suite and record the score.
  5. Grow brain  - once enough new data exists (and a base model is configured), train a LoRA
                   candidate (Aes 3.x). The owner promotes it only if its evals are better.
  6. Report      - progress report with the daily score trend.

Run: python main.py --daily   (or run_daily_training.bat, or install_daily_task.bat for every night)
"""
import json, subprocess, sys, time
from pathlib import Path
from .paths import REPORTS, EXPORTS, MODELS, BUNDLE_ROOT


class DailyTrainer:
    def __init__(self, db, agent, evals=None, training=None, log=print):
        from .evals import EvalRunner
        from .training import TrainingLab
        self.db = db; self.agent = agent; self.log = log
        self.evals = evals or EvalRunner(db, agent.runtimes)
        self.training = training or TrainingLab(db, EXPORTS)

    def _int(self, key, default):
        try: return int(self.db.setting(key, str(default)))
        except Exception: return default

    # 1 ------------------------------------------------------------------------
    def school(self, model_name):
        from .curriculum import queue_next
        from .autopilot import Autopilot
        added = queue_next(self.db, self._int('daily_units', 3))
        self.log(f'School: queued {added} new goal(s).')
        report = Autopilot(self.db, self.agent, log=self.log).run_all(model_name, max_goals=self._int('daily_max_goals', 12))
        return added, report

    # 2 + 3 --------------------------------------------------------------------
    def drills(self, model_name):
        from .drills import run_drills
        model = self.db.model(model_name)
        stats = run_drills(lambda msgs: self.agent._complete(model, msgs),
                           self._int('daily_math_drills', 20), self._int('daily_code_drills', 6), seed=int(time.time()))
        for msgs, source, quality in stats.pop('examples'):
            self.db.add_training_example(msgs, source, quality)
        self.log(f"Drills: maths {stats['math_ok']}/{stats['math_total']}, code {stats['code_ok']}/{stats['code_total']}")
        return stats

    def harvest(self):
        added = self.training.add_from_feedback()
        # Autopilot goals the strict reviewer judged DONE are good worked examples.
        for g in self.db.query("SELECT * FROM goals WHERE status='done' AND kind='task' AND conversation_id IS NOT NULL"):
            src = f"autopilot:{g['id']}"
            if self.db.one('SELECT id FROM training_examples WHERE source=?', (src,)): continue
            msgs = [{'role': m['role'], 'content': m['content']} for m in self.db.messages(g['conversation_id']) if m['role'] in ('user', 'assistant')]
            if len(msgs) >= 2:
                self.db.add_training_example(msgs[-12:], src, 2); added += 1
        return added

    # 4 ------------------------------------------------------------------------
    def exam(self, model_name):
        try:
            score, passed, total, _ = self.evals.run(model_name)
            return score, passed, total
        except Exception as e:
            self.log(f'Exam skipped: {e}'); return None, 0, 0

    # 5 ------------------------------------------------------------------------
    def grow_brain(self):
        base = self.db.setting('daily_lora_base', '').strip()
        if self.db.setting('daily_lora_enabled', '0') != '1' or not base:
            return 'LoRA training is off (set daily_lora_enabled=1 and daily_lora_base in Settings).'
        last = float(self.db.setting('daily_lora_last', '0') or 0)
        fresh = self.db.one('SELECT COUNT(*) c FROM training_examples WHERE created_at>? AND quality>=2', (last,))['c']
        need = self._int('daily_lora_min_examples', 300)
        if fresh < need:
            return f'Collecting data: {fresh}/{need} new high-quality examples before the next brain training.'
        dataset, n = self.training.export_jsonl(f'aes_daily_{time.strftime("%Y%m%d")}.jsonl')
        out = Path(MODELS) / f'aes-lora-{time.strftime("%Y%m%d")}'
        script = BUNDLE_ROOT / 'trainer' / 'train_lora.py'
        py = sys.executable if not getattr(sys, 'frozen', False) else 'python'
        self.log(f'Training LoRA on {n} examples -> {out} (this can take hours)')
        cp = subprocess.run([py, str(script), '--base', base, '--dataset', str(dataset), '--output', str(out), '--epochs', '2'] + self.db.setting('daily_lora_args', '--qlora --max-seq 2048').split(),
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
        if cp.returncode != 0:
            return f'LoRA training failed (exit {cp.returncode}):\n{(cp.stdout + cp.stderr)[-3000:]}'
        self.db.set_setting('daily_lora_last', str(time.time()))
        cid = self.db.add_candidate(f'Aes 3.x LoRA {time.strftime("%Y-%m-%d")}', base, 'lora',
                                    {'adapter': str(out), 'dataset': str(dataset), 'examples': n}, 'needs_eval')
        return (f'Trained LoRA candidate #{cid} at {out}. Next: merge_lora.py -> convert to GGUF -> add a llama_cpp profile -> '
                'run Evals; promote only if the score beats the current brain.')

    # all ------------------------------------------------------------------------
    def run(self, model_name, school=True):
        started = time.time(); log = []
        added = report = None
        if school:
            added, report = self.school(model_name)
        drill = self.drills(model_name)
        harvested = self.harvest()
        score, passed, total = self.exam(model_name)
        brain = self.grow_brain()
        day = {'date': time.strftime('%Y-%m-%d'), 'model': model_name, 'math': [drill['math_ok'], drill['math_total']],
               'code': [drill['code_ok'], drill['code_total']], 'eval': score, 'harvested': harvested}
        history = json.loads(self.db.setting('daily_history', '[]') or '[]')[-59:] + [day]
        self.db.set_setting('daily_history', json.dumps(history))
        path = Path(REPORTS) / f'daily_{time.strftime("%Y-%m-%d_%H%M")}.md'
        pct = lambda a, b: f'{(100 * a / b):.0f}%' if b else '-'
        lines = [f'# Aes daily training — {day["date"]}', '',
                 f'Brain: {model_name}  ·  Duration: {int((time.time() - started) / 60)} min', '',
                 '## Today', '',
                 f'- Curriculum goals queued: {added if added is not None else "skipped"}' + (f'  (autopilot report: {report.name})' if report else ''),
                 f'- Maths/science drills: {drill["math_ok"]}/{drill["math_total"]} ({pct(drill["math_ok"], drill["math_total"])})',
                 f'- Code drills (hidden tests): {drill["code_ok"]}/{drill["code_total"]} ({pct(drill["code_ok"], drill["code_total"])})',
                 f'- Evals: {"-" if score is None else f"{score:.0f}% ({passed}/{total})"}',
                 f'- New training examples harvested: {harvested} (+ drills)',
                 f'- Total training examples: {len(self.db.training_examples())}',
                 f'- Brain growth: {brain}', '',
                 '## Trend (last 14 days)', '', '| Date | Maths | Code | Evals |', '|---|---|---|---|']
        for h in history[-14:]:
            ev = '-' if h['eval'] is None else f"{h['eval']:.0f}%"
            lines.append(f"| {h['date']} | {pct(*h['math'])} | {pct(*h['code'])} | {ev} |")
        path.write_text('\n'.join(lines), encoding='utf-8')
        self.db.log('daily_training', f'{path.name}: math {drill["math_ok"]}/{drill["math_total"]} code {drill["code_ok"]}/{drill["code_total"]}', True)
        self.log(f'Daily report: {path}')
        return path
