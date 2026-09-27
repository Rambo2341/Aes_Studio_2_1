from __future__ import annotations
import re
class MemoryStore:
    def __init__(self,db): self.db=db
    def search(self,query,limit=8):
        toks=set(re.findall(r'[\w\u0600-\u06FF]{3,}',(query or '').lower()))
        scored=[]
        for r in self.db.memories():
            text=(r['text']+' '+(r['tags'] or '')).lower()
            hit=sum(1 for t in toks if t in text)
            if hit: scored.append((hit*10+int(r['importance']),r))
        return [r for _,r in sorted(scored,key=lambda x:x[0],reverse=True)[:limit]]
