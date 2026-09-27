from __future__ import annotations
import re
from pathlib import Path

TEXT_EXT={'.txt','.md','.rst','.py','.java','.js','.ts','.tsx','.jsx','.json','.yaml','.yml','.toml','.ini','.cfg','.xml','.html','.css','.scss','.lua','.luau','.cs','.cpp','.c','.h','.hpp','.gradle','.properties','.log'}

def chunks(text, size=3500, overlap=350):
    text=text.replace('\x00',' ')
    if len(text)<=size: return [text]
    out=[]; i=0
    while i<len(text):
        j=min(len(text),i+size)
        if j<len(text):
            cut=max(text.rfind('\n',i,j),text.rfind('. ',i,j))
            if cut>i+size//2: j=cut+1
        out.append(text[i:j])
        if j>=len(text): break
        i=max(i+1,j-overlap)
    return out

class KnowledgeBase:
    def __init__(self, db): self.db=db

    def extract(self, path: str | Path):
        p=Path(path); ext=p.suffix.lower()
        if ext in TEXT_EXT or ext=='':
            return p.read_text(encoding='utf-8',errors='replace'), 'text/plain'
        if ext=='.pdf':
            try:
                from pypdf import PdfReader
            except Exception as e:
                raise RuntimeError('PDF import needs pypdf. Install requirements-base.txt') from e
            reader=PdfReader(str(p)); return '\n\n'.join((page.extract_text() or '') for page in reader.pages), 'application/pdf'
        if ext=='.docx':
            try:
                from docx import Document
            except Exception as e: raise RuntimeError('DOCX import needs python-docx') from e
            d=Document(str(p)); return '\n'.join(x.text for x in d.paragraphs), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        raise RuntimeError(f'Unsupported knowledge file: {ext}')

    def import_file(self,path):
        p=Path(path); text,mime=self.extract(p)
        if not text.strip(): raise RuntimeError('No readable text found in this file.')
        cur=self.db.execute('INSERT INTO knowledge_docs(name,source_path,mime,chars,created_at) VALUES(?,?,?,?,strftime("%s","now"))',(p.name,str(p),mime,len(text)))
        did=cur.lastrowid
        for i,ch in enumerate(chunks(text)):
            self.db.execute('INSERT INTO knowledge_chunks(doc_id,chunk_index,content) VALUES(?,?,?)',(did,i,ch))
        self.db.log('knowledge_import',f'{p.name}: {len(text)} chars',True)
        return did,len(text)

    def search(self,query,limit=6):
        query=(query or '').strip()
        if not query: return []
        # FTS first; fall back to keyword overlap.
        try:
            terms=' OR '.join(re.findall(r'[\w\u0600-\u06FF]{3,}',query)[:12])
            if terms:
                rows=self.db.query('''SELECT kc.id,kc.doc_id,kc.content,kd.name,bm25(knowledge_fts) rank
                    FROM knowledge_fts JOIN knowledge_chunks kc ON kc.id=knowledge_fts.rowid
                    JOIN knowledge_docs kd ON kd.id=kc.doc_id WHERE knowledge_fts MATCH ? ORDER BY rank LIMIT ?''',(terms,int(limit)))
                if rows: return rows
        except Exception: pass
        toks=set(re.findall(r'[\w\u0600-\u06FF]{3,}',query.lower()))
        scored=[]
        for r in self.db.query('''SELECT kc.id,kc.doc_id,kc.content,kd.name FROM knowledge_chunks kc JOIN knowledge_docs kd ON kd.id=kc.doc_id ORDER BY kc.id DESC LIMIT 1000'''):
            txt=r['content'].lower(); s=sum(1 for t in toks if t in txt)
            if s: scored.append((s,r))
        return [r for _,r in sorted(scored,key=lambda x:x[0],reverse=True)[:limit]]
