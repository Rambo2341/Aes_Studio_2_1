from __future__ import annotations
"""Aes Research Mode: one prompt -> Aes teaches itself a whole field, for hours.

  prompt ("Master Blender: modelling, rigging, animation")
    -> plan an ordered syllabus (fundamentals -> advanced)
    -> for each lesson: web articles + PDFs (learn), and tutorial videos (video_search + learn_from_video)
    -> after each lesson: propose follow-up lessons it discovered (the frontier) and keep going
    -> stop at the time budget / topic cap / STOP file, write a report

Everything read is archived raw in <data>/library/raw and summarised into the knowledge library.
"""
import json, re, time
from pathlib import Path
from .paths import REPORTS
from .autopilot import STOP_FILE


def _norm(t):
    return re.sub(r'\W+', ' ', (t or '').lower()).strip()


def _json_list(text):
    m = re.search(r'\[.*\]', text or '', re.S)
    if not m: return []
    try:
        items = json.loads(m.group(0))
    except Exception:
        return []
    return [str(x.get('topic') if isinstance(x, dict) else x).strip() for x in items if x]


class ResearchMode:
    def __init__(self, db, agent, log=print):
        self.db = db; self.agent = agent; self.log = log

    def _ask(self, model, prompt):
        return self.agent._complete(model, [{'role': 'system', 'content': 'You are Aes planning your own studies. Reply with JSON only.'},
                                            {'role': 'user', 'content': prompt}])

    def plan(self, model, goal, n=12):
        known = [r['name'] for r in self.db.docs()][:80]
        return _json_list(self._ask(model,
            f'Goal: {goal}\nCreate a syllabus of {n} lessons ordered from absolute fundamentals to advanced/expert. '
            'Each lesson must be a concrete, searchable topic (e.g. "Blender UV unwrapping with seams"). '
            f'Skip what is already studied: {known}\nReturn a JSON array of strings.'))

    def expand(self, model, goal, lesson, notes, n=3):
        return _json_list(self._ask(model,
            f'Overall goal: {goal}\nJust studied: {lesson}\nNotes excerpt:\n{notes[:3000]}\n'
            f'Propose up to {n} NEW follow-up lessons that fill gaps or go deeper. JSON array of strings.'))

    def run(self, model_name, goal, hours=1.0, max_topics=None, videos=True):
        model = self.db.model(model_name)
        if not model: raise RuntimeError(f'Model profile not found: {model_name}')
        deadline = time.time() + float(hours) * 3600
        max_topics = int(max_topics or max(5, int(float(hours) * 8)))
        queue = self.plan(model, goal) or [goal]
        seen = {_norm(t) for t in queue}; done = []
        self.log(f'Research plan ({len(queue)} lessons): ' + ' | '.join(queue[:12]))
        while queue and len(done) < max_topics and time.time() < deadline:
            if STOP_FILE.exists() or self.db.setting('autopilot_stop', '0') == '1':
                self.log('Stop requested.'); break
            lesson = queue.pop(0)
            self.log(f'[{len(done)+1}/{max_topics}] Studying: {lesson}')
            result = self.agent.learn(model_name, lesson, 2)
            video_note = ''
            if videos and not result.startswith(('ERROR', 'Could not')):
                try:
                    hits = self.agent.tools._video_search(lesson, 3)
                    url = next((l.strip() for l in hits.splitlines() if l.strip().startswith('http')), None)
                    if url:
                        v = self.agent.learn_from_video(model_name, url, lesson)
                        video_note = '' if v.startswith('ERROR') else f' + video {url}'
                except Exception:
                    pass
            ok = not result.startswith(('ERROR', 'Could not'))
            done.append((lesson, ok, video_note, result))
            if ok:
                for t in self.expand(model, goal, lesson, result):
                    if _norm(t) not in seen:
                        seen.add(_norm(t)); queue.append(t)
        return self.report(goal, model_name, done, queue)

    def report(self, goal, model_name, done, queue):
        p = Path(REPORTS) / f'research_{time.strftime("%Y-%m-%d_%H%M")}.md'
        ok = sum(1 for _, good, _, _ in done if good)
        lines = [f'# Aes Research Mode — {goal}', '', f'Brain: {model_name} · Lessons studied: {ok}/{len(done)}', '', '## Lessons', '']
        lines += [f'- {"✅" if good else "❌"} {lesson}{vid}' for lesson, good, vid, _ in done]
        if queue:
            lines += ['', '## Next lessons discovered (not yet studied)', ''] + [f'- {t}' for t in queue[:40]]
        p.write_text('\n'.join(lines), encoding='utf-8')
        self.db.add_memory(f'Research Mode on "{goal}": studied {ok} lessons; report {p.name}.', 'research', 'lesson', 3)
        self.db.log('research', f'{goal}: {ok}/{len(done)} -> {p.name}', True)
        return p
