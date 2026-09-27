from __future__ import annotations
"""Aes training curriculum: turns curriculum/*.json into Autopilot goals.

Each unit becomes two goals: a study goal (learn the topic from its sources + the web)
and a practice goal (do a real exercise with a Definition of Done). Aes then studies
like a student: primary -> middle -> high-school -> university -> specialist.
"""
import json
from pathlib import Path
from .paths import RESOURCE_ROOT

CURRICULUM_DIR = RESOURCE_ROOT / 'curriculum'
LEVELS = ['primary', 'middle', 'high-school', 'university', 'specialist']


def load(path=None):
    p = Path(path) if path else CURRICULUM_DIR / 'aes_curriculum.json'
    return json.loads(p.read_text(encoding='utf-8'))


def tracks(path=None):
    return sorted({u['track'] for u in load(path)['units']})


def queue(db, track=None, max_level=None, path=None, practice=True):
    """Queue curriculum units (skipping ones already queued/done). Returns number of goals added."""
    units = load(path)['units']
    if track and track != 'all':
        units = [u for u in units if u['track'] in {t.strip() for t in track.split(',')}]
    if max_level:
        units = [u for u in units if LEVELS.index(u['level']) <= LEVELS.index(max_level)]
    units.sort(key=lambda u: LEVELS.index(u['level']))
    existing = {g['title'] for g in db.goals()}
    added = 0
    for u in units:
        study = f"[{u['id']}] Study: {u['topic']}"
        if study not in existing:
            db.add_goal(study, 'Sources: ' + ' '.join(u.get('sources', [])), 'learn'); added += 1
        if practice:
            prac = f"[{u['id']}] Practice: {u['practice']}"
            if prac not in existing:
                db.add_goal(prac, f"Level: {u['level']}. First use recall for the '{u['topic']}' study notes.\n"
                                  f"Definition of Done: {u['done']}\n"
                                  "Work inside the workspace folder Aes_Practice. When finished, remember one lesson learned.", 'task'); added += 1
    return added


def queue_next(db, k=3, path=None):
    """Advance the school year: queue the next k units nobody has started yet,
    lowest level first and alternating tracks, so Aes grows evenly in every field."""
    units = load(path)['units']
    started = {g['title'].split(']')[0] + ']' for g in db.goals() if g['title'].startswith('[')}
    todo = [u for u in units if f"[{u['id']}]" not in started]
    todo.sort(key=lambda u: (LEVELS.index(u['level']), [x['track'] for x in units].index(u['track'])))
    picked = []; seen_tracks = set()
    for u in todo:                        # first pass: one per track at the lowest level
        if len(picked) >= k: break
        if u['track'] not in seen_tracks and LEVELS.index(u['level']) == LEVELS.index(todo[0]['level']):
            picked.append(u); seen_tracks.add(u['track'])
    for u in todo:                        # fill the rest in order
        if len(picked) >= k: break
        if u not in picked: picked.append(u)
    added = 0
    for u in picked:
        db.add_goal(f"[{u['id']}] Study: {u['topic']}", 'Sources: ' + ' '.join(u.get('sources', [])), 'learn')
        db.add_goal(f"[{u['id']}] Practice: {u['practice']}",
                    f"Level: {u['level']}. First use recall for the '{u['topic']}' study notes.\nDefinition of Done: {u['done']}\n"
                    "Work inside the workspace folder Aes_Practice. When finished, remember one lesson learned.", 'task')
        added += 2
    return added
