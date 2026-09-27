from __future__ import annotations
import argparse,json
from pathlib import Path

TEXT={'.txt','.md','.rst','.py','.java','.js','.ts','.tsx','.jsx','.json','.yaml','.yml','.toml','.ini','.cfg','.xml','.html','.css','.lua','.luau','.cs','.cpp','.c','.h','.hpp'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--chunk',type=int,default=6000);a=p.parse_args()
    root=Path(a.input);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);count=0
    with out.open('w',encoding='utf-8') as f:
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in TEXT:continue
            try:text=path.read_text(encoding='utf-8',errors='ignore')
            except Exception:continue
            for i in range(0,len(text),a.chunk):
                chunk=text[i:i+a.chunk].strip()
                if len(chunk)<200:continue
                f.write(json.dumps({'text':chunk,'source':str(path.relative_to(root))},ensure_ascii=False)+'\n');count+=1
    print('Wrote',count,'chunks to',out)
if __name__=='__main__':main()
