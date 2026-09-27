from __future__ import annotations
import json,time
from pathlib import Path

class TrainingLab:
    def __init__(self,db,exports): self.db=db; self.exports=Path(exports); self.exports.mkdir(parents=True,exist_ok=True)
    def add_from_feedback(self):
        added=0
        for f in self.db.query('SELECT * FROM feedback WHERE rating>0 ORDER BY id'):
            exists=self.db.one("SELECT id FROM training_examples WHERE source=?",(f"feedback:{f['id']}",))
            if exists: continue
            msgs=self.db.messages(f['conversation_id'])
            target=next((i for i,m in enumerate(msgs) if m['id']==f['message_id']),None)
            if target is None: continue
            start=max(0,target-6); arr=[{'role':m['role'],'content':m['content']} for m in msgs[start:target+1] if m['role'] in ('user','assistant')]
            if len(arr)>=2:
                self.db.add_training_example(arr,f"feedback:{f['id']}",quality=2); added+=1
        return added
    def export_jsonl(self,filename=None):
        filename=filename or f"aes_training_{int(time.time())}.jsonl"; p=self.exports/filename
        rows=self.db.training_examples()
        with p.open('w',encoding='utf-8') as f:
            for r in rows:
                obj={'messages':json.loads(r['messages_json']),'metadata':{'source':r['source'],'quality':r['quality']}}
                f.write(json.dumps(obj,ensure_ascii=False)+'\n')
        return p,len(rows)
    def create_candidate(self,name,base_model,notes=''):
        payload={'notes':notes,'training_examples':len(self.db.training_examples()),'created_by':'Aes Studio Training Lab'}
        return self.db.add_candidate(name,base_model,'lora',payload,'draft',None)
