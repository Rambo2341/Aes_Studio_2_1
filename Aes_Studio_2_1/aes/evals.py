from __future__ import annotations
import re

class EvalRunner:
    def __init__(self,db,runtimes): self.db=db; self.runtimes=runtimes
    def score_prompt(self,model,system_prompt):
        details=[]; passed=0; cases=self.db.eval_cases()
        sys=system_prompt+'\n\nEVAL MODE: answer the user directly, briefly and accurately. Do not use tools.'
        for c in cases:
            ans=self.runtimes.complete(model,[{'role':'system','content':sys},{'role':'user','content':c['prompt']}])
            low=ans.lower()
            exp=[x.strip().lower() for x in c['expected_keywords'].split(',') if x.strip()]
            bad=[x.strip().lower() for x in c['forbidden_keywords'].split(',') if x.strip()]
            hits=sum(1 for x in exp if x in low); forbidden=any(x in low for x in bad)
            ok=(hits>=max(1,(len(exp)+1)//2) if exp else True) and not forbidden
            passed += int(ok)
            details.append({'name':c['name'],'passed':ok,'answer':ans[:1500],'expected':exp,'forbidden':bad})
        total=len(cases); score=(passed/total*100.0) if total else 0.0
        return score,passed,total,details

    def run(self,model_name):
        model=self.db.model(model_name)
        if not model: raise RuntimeError('Model profile not found')
        score,passed,total,details=self.score_prompt(model,model['system_prompt'])
        self.db.add_eval_run(model_name,score,passed,total,details)
        return score,passed,total,details
