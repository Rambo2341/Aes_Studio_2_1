from __future__ import annotations
import json, time

class EvolutionManager:
    """Stages evidence-based Aes improvements; it never silently publishes them."""
    def __init__(self,db,runtimes,evals,training):
        self.db=db; self.runtimes=runtimes; self.evals=evals; self.training=training

    def maybe_stage(self,model_name):
        if self.db.setting('auto_evolve','1')!='1': return None
        minimum=max(2,int(self.db.setting('auto_evolve_min_feedback','8') or 8))
        feedback=self.db.feedback(500)
        last=self.db.one("SELECT MAX(created_at) AS t FROM candidates WHERE kind='prompt-evolution'")
        last_t=(last['t'] if last and last['t'] else 0)
        fresh=[r for r in feedback if r['created_at']>last_t]
        if len(fresh)<minimum: return None
        model=self.db.model(model_name)
        if not model: return None
        notes=[]
        for f in fresh[:40]:
            notes.append(f"rating={f['rating']} note={f['note'] or '(no note)'}")
        prompt=(
          "Improve the following Aes system prompt using the owner feedback. Preserve tool honesty, permission checks, privacy, "
          "and general capability. Do not add hidden permissions. Return only the complete revised system prompt.\n\nCURRENT:\n"+
          model['system_prompt']+"\n\nFEEDBACK:\n"+'\n'.join(notes)
        )
        revised=self.runtimes.complete(model,[{'role':'user','content':prompt}]).strip()
        if len(revised)<200: return None
        base_score=self.evals.score_prompt(model,model['system_prompt'])[0]
        new_score=self.evals.score_prompt(model,revised)[0]
        status='ready_for_owner' if new_score>=base_score else 'regressed'
        payload={'system_prompt':revised,'base_score':base_score,'candidate_score':new_score,'feedback_count':len(fresh)}
        cid=self.db.add_candidate(f"{model_name} prompt evolution {int(time.time())}",model_name,'prompt-evolution',payload,status,new_score)
        self.training.add_from_feedback()
        self.db.log('auto_evolve',f'candidate={cid} base={base_score:.1f} new={new_score:.1f} status={status}',new_score>=base_score)
        return cid,status,base_score,new_score
