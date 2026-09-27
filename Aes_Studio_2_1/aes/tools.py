from __future__ import annotations
from dataclasses import dataclass
import json, os, re, shlex, subprocess, sys, tempfile, time, urllib.request, urllib.parse, html, webbrowser
from pathlib import Path
from .security import RISK_SAFE,RISK_WRITE,RISK_EXEC,RISK_NETWORK,RISK_COMPUTER,RISK_SYSTEM

@dataclass
class Tool:
    name: str
    description: str
    risk: str
    schema: dict
    fn: callable

class ToolError(RuntimeError): pass

CHROME_WINDOWS=[os.path.expandvars(p) for p in (r'%ProgramFiles%\Google\Chrome\Application\chrome.exe',
    r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe', r'%LocalAppData%\Google\Chrome\Application\chrome.exe')]

class ToolRegistry:
    def __init__(self, workspace: str | Path, db, permission_manager):
        self.workspace=Path(workspace).resolve(); self.workspace.mkdir(parents=True,exist_ok=True)
        self.db=db; self.permission=permission_manager; self.tools={}
        self._register_builtin()

    def set_workspace(self,path):
        p=Path(path).expanduser().resolve(); p.mkdir(parents=True,exist_ok=True); self.workspace=p

    def register(self,t:Tool): self.tools[t.name]=t
    def describe(self,allowed=None):
        rows=[]
        for name,t in self.tools.items():
            if allowed is not None and name not in allowed: continue
            rows.append(f"- {name}: {t.description} | arguments={json.dumps(t.schema,ensure_ascii=False)} | risk={t.risk}")
        return '\n'.join(rows)
    def call(self,name,args,allowed=None):
        if name not in self.tools: raise ToolError(f'Unknown tool: {name}')
        if allowed is not None and name not in allowed: raise ToolError(f"Tool '{name}' is not allowed in this agent role")
        t=self.tools[name]
        summary=f"{name}({', '.join(f'{k}={str(v)[:80]}' for k,v in (args or {}).items())})"
        self.permission.authorize(name,t.risk,summary,args or {})
        try:
            out=t.fn(**(args or {}))
            self.db.log('tool_call',summary,True)
            return str(out)
        except Exception as e:
            self.db.log('tool_call',summary+f' -> {e}',False)
            raise

    def _safe(self,rel):
        rel=rel or '.'
        p=(self.workspace/rel).resolve()
        if self.workspace!=p and self.workspace not in p.parents: raise ToolError('Path escapes the active Aes workspace')
        return p
    def _backup(self,p):
        if not p.exists() or not p.is_file(): return None
        import time, shutil
        bdir=self.workspace/'.aes_backups'/time.strftime('%Y%m%d_%H%M%S'); target=bdir/p.relative_to(self.workspace); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,target); return target
    def _list_files(self,path='.'):
        p=self._safe(path)
        if not p.exists(): return 'Not found'
        if p.is_file(): return f'FILE {p.name} ({p.stat().st_size} bytes)'
        out=[]
        for x in sorted(p.iterdir(),key=lambda q:(not q.is_dir(),q.name.lower()))[:500]:
            out.append(('DIR  ' if x.is_dir() else 'FILE ')+x.name)
        return '\n'.join(out) or '(empty)'
    def _read_file(self,path,start_line=1,end_line=400):
        p=self._safe(path)
        text=p.read_text(encoding='utf-8',errors='replace').splitlines()
        s=max(1,int(start_line)); e=min(len(text),int(end_line))
        return '\n'.join(f'{i+1:>5}: {text[i]}' for i in range(s-1,e))
    def _search_text(self,query,path='.'):
        base=self._safe(path); rx=re.compile(re.escape(query),re.I); out=[]
        files=[base] if base.is_file() else [p for p in base.rglob('*') if p.is_file()]
        for p in files[:3000]:
            try:
                if p.stat().st_size>2_000_000: continue
                for i,line in enumerate(p.read_text(encoding='utf-8',errors='ignore').splitlines(),1):
                    if rx.search(line):
                        out.append(f'{p.relative_to(self.workspace)}:{i}: {line[:300]}')
                        if len(out)>=200: return '\n'.join(out)
            except Exception: continue
        return '\n'.join(out) or '(no matches)'
    def _write_file(self,path,content):
        p=self._safe(path); p.parent.mkdir(parents=True,exist_ok=True)
        before=p.read_text(encoding='utf-8',errors='replace') if p.exists() else None
        self._backup(p)
        p.write_text(content,encoding='utf-8')
        return f"Wrote {len(content)} chars to {p.relative_to(self.workspace)}" + (f" (replaced {len(before)} chars)" if before is not None else '')
    def _replace_text(self,path,old,new,count=1):
        p=self._safe(path); text=p.read_text(encoding='utf-8',errors='replace')
        if old not in text: raise ToolError('Target text was not found; no change made')
        self._backup(p)
        newtext=text.replace(old,new,int(count)); p.write_text(newtext,encoding='utf-8')
        return f'Replaced {min(int(count),text.count(old))} occurrence(s) in {p.relative_to(self.workspace)}'
    BLOCKED=['format ','diskpart','shutdown','reboot','rm -rf /','rm -rf ~','del /s /q c:','rd /s /q c:','reg delete','bcdedit','cipher /w','mkfs.','dd if=','vssadmin delete']
    def _run(self,cmd,timeout=120,shell=False):
        parts=shlex.split(cmd,posix=(os.name!='nt'))
        if not parts: raise ToolError('Empty command')
        lowered=(' '.join(parts)+' '+cmd).lower()
        if any(x in lowered for x in self.BLOCKED): raise ToolError('A destructive system command was blocked')
        use_shell=str(shell).lower() in ('1','true','yes')
        cp=subprocess.run(cmd if use_shell else parts,cwd=self.workspace,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(1,min(int(timeout),3600)),shell=use_shell)
        out=(cp.stdout or '') + (('\n'+cp.stderr) if cp.stderr else '')
        return f'exit={cp.returncode}\n{out[-30000:]}'
    def _git_status(self): return self._run('git status --short')
    def _git_diff(self): return self._run('git diff -- .')
    def _fetch_url(self,url,max_chars=30000,render=False):
        if str(render).lower() in ('1','true','yes'):
            return f'url={url}\nrendered=true\n{self._render_page(url)[:int(max_chars)]}'
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AesStudio/2.2'})
        with urllib.request.urlopen(req,timeout=30) as r:
            ctype=r.headers.get('content-type','')
            limit=40_000_000 if ('pdf' in ctype.lower() or str(url).lower().endswith('.pdf')) else min(int(max_chars)*4,2_000_000)
            data=r.read(limit)
        if 'pdf' in ctype.lower() or data[:5]==b'%PDF-':
            return f'url={url}\ncontent-type=application/pdf\n{pdf_bytes_to_text(data)[:int(max_chars)]}'
        text=data.decode('utf-8',errors='replace')
        if 'html' in ctype.lower() or text.lstrip().lower().startswith(('<!doctype html','<html')):
            text=html_to_text(text)
        return f'url={url}\ncontent-type={ctype}\n{text[:int(max_chars)]}'
    def _web_search(self,query,max_results=8):
        q=urllib.parse.urlencode({'q':query})
        url='https://html.duckduckgo.com/html/?'+q
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AesStudio/2.1'})
        with urllib.request.urlopen(req,timeout=25) as r:
            text=r.read(1_500_000).decode('utf-8',errors='replace')
        rx=re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',re.I|re.S)
        out=[]
        for href,title in rx.findall(text):
            title=re.sub(r'<[^>]+>',' ',title); title=html.unescape(re.sub(r'\s+',' ',title)).strip()
            href=html.unescape(href)
            try:
                parsed=urllib.parse.urlparse(href)
                if parsed.netloc.endswith('duckduckgo.com'):
                    target=urllib.parse.parse_qs(parsed.query).get('uddg',[''])[0]
                    if target: href=urllib.parse.unquote(target)
            except Exception: pass
            if title and href:
                out.append(f'{len(out)+1}. {title}\n   {href}')
            if len(out)>=max(1,min(int(max_results),15)): break
        return '\n'.join(out) or '(no search results parsed)'
    def _remember(self,text,tags='',kind='lesson',importance=2):
        mid=self.db.add_memory(str(text),str(tags),str(kind),max(1,min(int(importance),5)))
        return f'Saved memory #{mid}: {str(text)[:180]}'
    def _comfyui_submit(self,workflow_path):
        import urllib.parse
        p=self._safe(workflow_path); workflow=json.loads(p.read_text(encoding='utf-8'))
        base=self.db.setting('comfyui_url','http://127.0.0.1:8188').rstrip('/')
        parsed=urllib.parse.urlparse(base)
        if parsed.hostname not in ('127.0.0.1','localhost','::1'): raise ToolError('ComfyUI URL must be local-only')
        payload=json.dumps({'prompt':workflow}).encode('utf-8')
        req=urllib.request.Request(base+'/prompt',data=payload,headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=20) as r: data=r.read().decode('utf-8',errors='replace')
        return data[:5000]
    def _take_screenshot(self,filename='screenshot.png'):
        p=self._safe(filename)
        try:
            from PIL import ImageGrab
            img=ImageGrab.grab(all_screens=True); img.save(p)
            return f'Saved screenshot to {p}'
        except Exception as e: raise ToolError(f'Screenshot unavailable: {e}')
    def _mouse_click(self,x,y,button='left',clicks=1):
        self._gui().click(int(x),int(y),clicks=int(clicks),button=button); return f'Clicked {button} x{clicks} at {x},{y}'
    def _launch_app(self,path,args=''):
        p=Path(path).expanduser()
        if not p.exists(): raise ToolError(f'Application not found: {p}')
        argv=[str(p)] + (shlex.split(args,posix=(os.name!='nt')) if args else [])
        proc=subprocess.Popen(argv,cwd=self.workspace)
        return f'Launched PID {proc.pid}: {p.name}'
    def _blender_run_script(self,script_path):
        blender=self.db.setting('blender_path','').strip() or 'blender'
        p=self._safe(script_path)
        cp=subprocess.run([blender,'--background','--python',str(p)],cwd=self.workspace,capture_output=True,text=True,timeout=600)
        return f'exit={cp.returncode}\n{((cp.stdout or "")+(cp.stderr or ""))[-30000:]}'
    def _unity_batch(self,project_path='.',execute_method=''):
        unity=self.db.setting('unity_path','').strip()
        if not unity: raise ToolError('Set the Unity Editor executable path in Settings first')
        proj=self._safe(project_path)
        args=[unity,'-batchmode','-quit','-projectPath',str(proj),'-logFile','-']
        if execute_method: args += ['-executeMethod',execute_method]
        cp=subprocess.run(args,cwd=self.workspace,capture_output=True,text=True,timeout=900)
        return f'exit={cp.returncode}\n{((cp.stdout or "")+(cp.stderr or ""))[-30000:]}'
    def _roblox_build(self,project_file='default.project.json',output='build.rbxlx'):
        rojo=self.db.setting('rojo_path','rojo').strip() or 'rojo'
        proj=self._safe(project_file); out=self._safe(output)
        cp=subprocess.run([rojo,'build',str(proj),'-o',str(out)],cwd=self.workspace,capture_output=True,text=True,timeout=300)
        return f'exit={cp.returncode}\n{((cp.stdout or "")+(cp.stderr or ""))[-30000:]}'

    def _task_create(self,title,detail=''):
        tid=self.db.add_task(title,detail); return f'Created task #{tid}: {title}'
    def _task_update(self,id,status='done',detail=None):
        ok=self.db.update_task(int(id),status,detail); return f'Task #{id} updated to {status}' if ok else f'Task #{id} not found'
    def _task_list(self):
        rows=self.db.tasks(); return '\n'.join(f"#{r['id']} [{r['status']}] {r['title']} — {r['detail']}" for r in rows) or '(no tasks)'


    # ---- computer use -------------------------------------------------------
    def _gui(self):
        try:
            import pyautogui
        except Exception as e: raise ToolError(f'pyautogui unavailable: {e}. Run: pip install pyautogui')
        pyautogui.FAILSAFE=True  # slam the mouse into a screen corner to abort
        return pyautogui
    def _screen_info(self):
        g=self._gui(); w,h=g.size(); x,y=g.position(); return f'screen={w}x{h} mouse=({x},{y})'
    def _look_at_screen(self,max_width=1600):
        try:
            from PIL import ImageGrab
            img=ImageGrab.grab(all_screens=False)
        except Exception as e: raise ToolError(f'Screenshot unavailable: {e}')
        w,h=img.size; scale=min(1.0,int(max_width)/float(w))
        if scale<1.0: img=img.resize((int(w*scale),int(h*scale)))
        shots=self.workspace/'.aes_screens'; shots.mkdir(parents=True,exist_ok=True)
        p=shots/f'screen_{time.strftime("%Y%m%d_%H%M%S")}.png'; img.save(p)
        return (f'Screenshot of the real screen ({w}x{h}). Image is scaled by {scale:.3f}; '
                f'to click a point seen at (ix,iy) in the image use x=ix/{scale:.3f}, y=iy/{scale:.3f}.\n[[aes-image:{p}]]')
    def _mouse_move(self,x,y,duration=0.2):
        self._gui().moveTo(int(x),int(y),duration=float(duration)); return f'Mouse moved to {x},{y}'
    def _mouse_drag(self,x,y,to_x,to_y,duration=0.4,button='left'):
        g=self._gui(); g.moveTo(int(x),int(y)); g.dragTo(int(to_x),int(to_y),duration=float(duration),button=button); return f'Dragged {x},{y} -> {to_x},{to_y}'
    def _mouse_scroll(self,amount,x=None,y=None):
        g=self._gui()
        if x is not None and y is not None: g.moveTo(int(x),int(y))
        g.scroll(int(amount)); return f'Scrolled {amount}'
    def _key_press(self,keys):
        g=self._gui(); combo=[k.strip().lower() for k in str(keys).replace(' ','').split('+') if k.strip()]
        if not combo: raise ToolError('No keys given')
        if len(combo)==1: g.press(combo[0])
        else: g.hotkey(*combo)
        return f'Pressed {"+".join(combo)}'
    def _keyboard_write(self,text,interval=0.01):
        g=self._gui()
        if all(ord(c)<128 for c in str(text)):
            g.write(text,interval=float(interval)); return f'Typed {len(text)} characters'
        # Non-ASCII (Arabic etc.): paste through the clipboard.
        self._clipboard_set(text); g.hotkey('command' if sys.platform=='darwin' else 'ctrl','v')
        return f'Pasted {len(text)} characters'
    def _clipboard_get(self):
        try:
            import pyperclip; return pyperclip.paste()
        except Exception as e: raise ToolError(f'Clipboard unavailable: {e}. Run: pip install pyperclip')
    def _clipboard_set(self,text):
        try:
            import pyperclip; pyperclip.copy(str(text)); return f'Clipboard set ({len(str(text))} chars)'
        except Exception as e: raise ToolError(f'Clipboard unavailable: {e}. Run: pip install pyperclip')
    def _open_url(self,url,browser='default'):
        if not re.match(r'^https?://',str(url)): raise ToolError('Only http(s) URLs can be opened')
        if browser=='chrome':
            for c in (CHROME_WINDOWS if os.name=='nt' else ['google-chrome','chromium']):
                try:
                    subprocess.Popen([c,url]); return f'Opened in Chrome: {url}'
                except Exception: continue
        webbrowser.open(url); return f'Opened: {url}'

    # ---- reading: pages, documents, magazines, videos --------------------------
    def _render_page(self,url):
        """Open the page in a real (headless) Chromium so JavaScript-heavy sites can be read."""
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise ToolError('Rendering needs Playwright: pip install playwright && python -m playwright install chromium') from e
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True)
            try:
                page=b.new_page(); page.goto(url,wait_until='networkidle',timeout=45000)
                return page.inner_text('body')
            finally: b.close()
    def _resolve_any(self,path):
        """Workspace-relative paths, or absolute paths anywhere on the owner PC (read-only use)."""
        p=Path(os.path.expandvars(str(path))).expanduser()
        return p.resolve() if p.is_absolute() else self._safe(str(path))
    def _read_document(self,path,start_char=0,max_chars=30000,save=False):
        from .knowledge import KnowledgeBase
        kb=KnowledgeBase(self.db); p=self._resolve_any(path)
        if not p.is_file(): raise ToolError(f'File not found: {p}')
        text,_=kb.extract(p)
        note=''
        if str(save).lower() in ('1','true','yes'):
            did,_=kb.import_text(p.name,text,str(p)); note=f' | saved to knowledge doc #{did}'
        s0=max(0,int(start_char)); chunk=text[s0:s0+int(max_chars)]
        more=f'\n... ({len(text)-s0-len(chunk)} more chars; call again with start_char={s0+len(chunk)})' if s0+len(chunk)<len(text) else ''
        return f'{p.name}: {len(text)} chars{note}\n{chunk}{more}'
    def _library_import(self,folder,recursive=True):
        """Import every readable book/magazine/doc in a folder into the knowledge library."""
        from .knowledge import KnowledgeBase, TEXT_EXT
        kb=KnowledgeBase(self.db); base=self._resolve_any(folder)
        if not base.is_dir(): raise ToolError(f'Folder not found: {base}')
        known={r['source_path'] for r in self.db.docs()}
        exts=TEXT_EXT|{'.pdf','.docx'}; it=base.rglob('*') if str(recursive).lower() not in ('0','false','no') else base.glob('*')
        done=[]; failed=[]
        for p in sorted(it):
            if not p.is_file() or p.suffix.lower() not in exts or str(p) in known: continue
            try: kb.import_file(p); done.append(p.name)
            except Exception as e: failed.append(f'{p.name}: {e}')
            if len(done)>=500: break
        return f'Imported {len(done)} file(s) from {base}.' + (f'\nFirst: {", ".join(done[:15])}' if done else '') + (f'\nFailed: {"; ".join(failed[:10])}' if failed else '')
    def _video_search(self,query,max_results=5):
        """Find tutorial videos (YouTube) for a topic."""
        hits=self._web_search(f'{query} tutorial site:youtube.com',max_results=15)
        urls=[l.strip() for l in hits.splitlines() if l.strip().startswith('http') and youtube_id(l.strip())]
        titles={}
        lines=hits.splitlines()
        for i,l in enumerate(lines):
            if l.strip() in urls and i>0: titles[l.strip()]=re.sub(r'^\d+\.\s*','',lines[i-1]).strip()
        out=[f'{titles.get(u,"video")}\n   {u}' for u in list(dict.fromkeys(urls))[:int(max_results)]]
        return '\n'.join(out) or '(no videos found)'
    def _video_transcript(self,source,language='ar,en',max_chars=60000):
        """Transcript of a YouTube/online video (subtitles) or a local audio/video file (Whisper)."""
        langs=[x.strip() for x in str(language).split(',') if x.strip()] or ['en']
        src=str(source).strip()
        if re.match(r'^https?://',src):
            text=youtube_transcript(src,langs) or ytdlp_subtitles(src,langs,self.workspace)
            if not text: raise ToolError('No subtitles found. Install yt-dlp + faster-whisper to transcribe audio, or try another video.')
        else:
            text=whisper_transcribe(self._resolve_any(src))
        return f'source={src}\nchars={len(text)}\n{text[:int(max_chars)]}'

    # ---- reasoning helpers ---------------------------------------------------
    def _run_python(self,code,timeout=120):
        """Run Python in a separate process (math, data, quick experiments)."""
        fd,path=tempfile.mkstemp(suffix='.py',dir=str(self.workspace)); os.close(fd)
        try:
            Path(path).write_text(str(code),encoding='utf-8')
            cp=subprocess.run([sys.executable if not getattr(sys,'frozen',False) else 'python',path],cwd=self.workspace,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(1,min(int(timeout),1800)))
            out=(cp.stdout or '')+(('\n'+cp.stderr) if cp.stderr else '')
            return f'exit={cp.returncode}\n{out[-30000:]}'
        finally:
            try: os.remove(path)
            except Exception: pass

    # ---- memory & knowledge --------------------------------------------------
    def _recall(self,query,limit=8):
        from .memory import MemoryStore
        from .knowledge import KnowledgeBase
        mem=MemoryStore(self.db).search(query,int(limit)); docs=KnowledgeBase(self.db).search(query,4)
        out=[f"[memory #{r['id']} {r['kind']}] {r['text']}" for r in mem]
        out+=[f"[knowledge: {r['name']}]\n{r['content'][:1500]}" for r in docs]
        return '\n\n'.join(out) or '(nothing stored about this yet)'
    def _knowledge_add(self,title,content,source=''):
        from .knowledge import KnowledgeBase
        did,n=KnowledgeBase(self.db).import_text(title,content,source); return f'Stored knowledge doc #{did} "{title}" ({n} chars)'
    def _goal_add(self,title,detail='',kind='task'):
        gid=self.db.add_goal(title,detail,kind if kind in ('task','learn','video','research') else 'task'); return f'Queued autopilot goal #{gid}: {title}'
    def _self_status(self):
        from .paths import APP_VERSION, DATA
        rows=self.db.query('SELECT COUNT(*) c FROM memories')[0]['c'],self.db.query('SELECT COUNT(*) c FROM knowledge_docs')[0]['c'],len(self.db.enabled_skills())
        goals=', '.join(f"{g['status']}:{g['c']}" for g in self.db.query("SELECT status,COUNT(*) c FROM goals GROUP BY status")) or 'none'
        tools=', '.join(self.tools)
        return (f'Aes Studio {APP_VERSION}\ndata_dir={DATA}\nworkspace={self.workspace}\nmemories={rows[0]} knowledge_docs={rows[1]} skills={rows[2]}\n'
                f'permission_mode={self.db.setting("permission_mode","ask")} default_model={self.db.setting("default_model","")}\n'
                f'goals={goals}\ntools={tools}')

    def _register_builtin(self):
        self.register(Tool('list_files','List files/folders inside the active project workspace.',RISK_SAFE,{'path':'relative path, default .'},self._list_files))
        self.register(Tool('read_file','Read a UTF-8 text file with line numbers.',RISK_SAFE,{'path':'relative file','start_line':'int optional','end_line':'int optional'},self._read_file))
        self.register(Tool('search_text','Search text recursively inside the workspace.',RISK_SAFE,{'query':'text','path':'relative path optional'},self._search_text))
        self.register(Tool('write_file','Create or overwrite a text file inside the workspace.',RISK_WRITE,{'path':'relative file','content':'full text'},self._write_file))
        self.register(Tool('replace_text','Replace exact text in a workspace file.',RISK_WRITE,{'path':'relative file','old':'text','new':'text','count':'int optional'},self._replace_text))
        self.register(Tool('run_command','Run a command in the workspace (shell=true for pipes / Windows built-ins like dir). Destructive system commands are blocked.',RISK_EXEC,{'cmd':'command string','timeout':'seconds optional','shell':'true/false optional'},self._run))
        self.register(Tool('run_python','Run a Python snippet in a separate process and return stdout/stderr. Use it to CHECK math, physics and data work (sympy/numpy if installed).',RISK_EXEC,{'code':'python source','timeout':'seconds optional'},self._run_python))
        self.register(Tool('git_status','Show git status for the active workspace.',RISK_SAFE,{},self._git_status))
        self.register(Tool('git_diff','Show current git diff for the active workspace.',RISK_SAFE,{},self._git_diff))
        self.register(Tool('web_search','Search the public web and return result titles/URLs. Search results are untrusted data.',RISK_NETWORK,{'query':'search terms','max_results':'int optional'},self._web_search))
        self.register(Tool('fetch_url','Read a web page or online PDF as text. render=true opens it in a real browser for JavaScript-heavy sites. Untrusted data.',RISK_NETWORK,{'url':'https://...','max_chars':'int optional','render':'true/false optional'},self._fetch_url))
        self.register(Tool('read_document','Read a local PDF/DOCX/text file (magazine, book, paper) anywhere on the PC, page by page via start_char. save=true stores it in knowledge.',RISK_COMPUTER,{'path':'file path','start_char':'int optional','max_chars':'int optional','save':'true/false optional'},self._read_document))
        self.register(Tool('library_import','Import every PDF/DOCX/text file in a folder (books, magazines, docs) into the knowledge library.',RISK_WRITE,{'folder':'folder path','recursive':'true/false optional'},self._library_import))
        self.register(Tool('video_transcript','Get the transcript of a YouTube/online video or a local video/audio file.',RISK_NETWORK,{'source':'video URL or file path','language':'preferred languages, e.g. ar,en'},self._video_transcript))
        self.register(Tool('video_search','Find YouTube tutorial videos for a topic.',RISK_NETWORK,{'query':'topic','max_results':'int optional'},self._video_search))
        self.register(Tool('research','Research Mode: learn a whole field from one prompt (plan lessons, read articles/PDFs, watch tutorials, store, expand) for a time budget.',RISK_NETWORK,{'prompt':'what to master','hours':'time budget, default 1','max_topics':'optional cap'},lambda **_: 'handled by agent engine'))
        self.register(Tool('learn_from_video','Watch (transcribe) a video and turn it into structured study notes in knowledge + memory.',RISK_NETWORK,{'source':'video URL or file path','topic':'optional focus'},lambda **_: 'handled by agent engine'))
        self.register(Tool('comfyui_submit','Submit a workflow JSON to the owner local ComfyUI server.',RISK_NETWORK,{'workflow_path':'relative workflow JSON'},self._comfyui_submit))
        self.register(Tool('take_screenshot','Capture the desktop to a PNG inside the workspace.',RISK_COMPUTER,{'filename':'relative png optional'},self._take_screenshot))
        self.register(Tool('mouse_click','Click a screen coordinate using the owner desktop.',RISK_COMPUTER,{'x':'int','y':'int','button':'left/right/middle','clicks':'1 or 2 optional'},self._mouse_click))
        self.register(Tool('keyboard_write','Type text into the currently focused application.',RISK_COMPUTER,{'text':'text','interval':'float optional'},self._keyboard_write))
        self.register(Tool('look_at_screen','Take a screenshot and SEE it (vision brains). Returns scale info for converting image coordinates to screen coordinates.',RISK_COMPUTER,{'max_width':'int optional'},self._look_at_screen))
        self.register(Tool('screen_info','Screen size and current mouse position.',RISK_SAFE,{},self._screen_info))
        self.register(Tool('mouse_move','Move the mouse to screen coordinates.',RISK_COMPUTER,{'x':'int','y':'int','duration':'seconds optional'},self._mouse_move))
        self.register(Tool('mouse_drag','Drag with the mouse from one point to another.',RISK_COMPUTER,{'x':'int','y':'int','to_x':'int','to_y':'int','button':'optional'},self._mouse_drag))
        self.register(Tool('mouse_scroll','Scroll the mouse wheel (positive=up).',RISK_COMPUTER,{'amount':'int','x':'optional','y':'optional'},self._mouse_scroll))
        self.register(Tool('key_press','Press a key or hotkey combo, e.g. enter, ctrl+s, alt+tab, ctrl+shift+esc.',RISK_COMPUTER,{'keys':'key or combo joined by +'},self._key_press))
        self.register(Tool('clipboard_get','Read the clipboard text.',RISK_COMPUTER,{},self._clipboard_get))
        self.register(Tool('clipboard_set','Put text on the clipboard.',RISK_COMPUTER,{'text':'text'},self._clipboard_set))
        self.register(Tool('open_url','Open a URL in the owner browser (browser=chrome to force Google Chrome).',RISK_COMPUTER,{'url':'https://...','browser':'default/chrome'},self._open_url))
        self.register(Tool('launch_app','Launch a specific executable path.',RISK_COMPUTER,{'path':'absolute executable path','args':'optional args'},self._launch_app))
        self.register(Tool('blender_run_script','Run a workspace Python script in Blender background mode.',RISK_EXEC,{'script_path':'relative .py file'},self._blender_run_script))
        self.register(Tool('unity_batch','Run Unity in batch mode for a workspace project.',RISK_EXEC,{'project_path':'relative project','execute_method':'optional C# method'},self._unity_batch))
        self.register(Tool('roblox_build','Build a Rojo Roblox project from the workspace.',RISK_EXEC,{'project_file':'relative .project.json','output':'relative output file'},self._roblox_build))
        self.register(Tool('task_create','Create a task in the Aes task ledger.',RISK_WRITE,{'title':'task title','detail':'optional detail'},self._task_create))
        self.register(Tool('task_update','Update an Aes task status/detail.',RISK_WRITE,{'id':'task id','status':'todo/doing/done/blocked','detail':'optional detail'},self._task_update))
        self.register(Tool('task_list','List the Aes task ledger.',RISK_SAFE,{},self._task_list))
        self.register(Tool('remember','Store a verified durable lesson/preference/project fact in Aes long-term memory.',RISK_WRITE,{'text':'memory text','tags':'comma-separated optional','kind':'fact/preference/project/procedure/lesson','importance':'1-5 optional'},self._remember))
        self.register(Tool('recall','Search Aes long-term memory and private knowledge for what Aes already learned.',RISK_SAFE,{'query':'what to look for','limit':'int optional'},self._recall))
        self.register(Tool('knowledge_add','Save a studied document/notes into the private knowledge library (with source).',RISK_WRITE,{'title':'title','content':'text','source':'url or origin'},self._knowledge_add))
        self.register(Tool('goal_add','Queue a goal for Autopilot to work on later (kind=task or learn).',RISK_WRITE,{'title':'short goal','detail':'outcome + definition of done','kind':'task/learn/video/research'},self._goal_add))
        self.register(Tool('self_status','Aes self-inspection: version, data folder, memory/knowledge counts, mode, tools.',RISK_SAFE,{},self._self_status))
        self.register(Tool('learn_topic','Study a topic from the web: search, read several sources, write verified notes into knowledge + memory.',RISK_NETWORK,{'topic':'what to learn','depth':'1-3 optional'},lambda **_: 'handled by agent engine'))
        self.register(Tool('delegate_agent','Delegate one focused lane to an Aes specialist sub-agent. Use this to keep the manager context clean.',RISK_SAFE,{'role':'explore/plan/research/code/blender/unity/roblox/review/computer/math','task':'focused task with outcome and completion criteria'},lambda **_: 'handled by agent engine'))


def html_to_text(raw: str) -> str:
    raw=re.sub(r'(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>',' ',raw)
    raw=re.sub(r'(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article)>','\n',raw)
    raw=re.sub(r'(?s)<[^>]+>',' ',raw)
    raw=html.unescape(raw)
    raw=re.sub(r'[ \t\r\f\v]+',' ',raw)
    raw=re.sub(r'\n\s*\n+','\n\n',raw)
    return raw.strip()


def pdf_bytes_to_text(data: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader
        return '\n\n'.join((pg.extract_text() or '') for pg in PdfReader(io.BytesIO(data)).pages)
    except Exception as e:
        return f'(PDF could not be read: {e})'

def youtube_id(url: str):
    m=re.search(r'(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})',url)
    return m.group(1) if m else None

def youtube_transcript(url, langs):
    vid=youtube_id(url)
    if not vid: return ''
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return ''
    for attempt in (langs, None):
        try:
            if hasattr(YouTubeTranscriptApi,'get_transcript'):   # 0.x API
                rows=YouTubeTranscriptApi.get_transcript(vid,languages=attempt) if attempt else YouTubeTranscriptApi.get_transcript(vid)
                return ' '.join(r['text'] for r in rows)
            api=YouTubeTranscriptApi()                             # 1.x API
            fetched=api.fetch(vid,languages=attempt) if attempt else api.fetch(vid)
            return ' '.join(s.text for s in fetched)
        except Exception:
            continue
    return ''

def vtt_to_text(vtt: str) -> str:
    out=[]; last=''
    for line in vtt.splitlines():
        line=line.strip()
        if not line or line=='WEBVTT' or '-->' in line or line.isdigit() or line.startswith(('Kind:','Language:','NOTE')): continue
        line=re.sub(r'<[^>]+>','',line)
        if line!=last: out.append(line); last=line
    return ' '.join(out)

def ytdlp_subtitles(url, langs, workdir):
    import shutil
    exe=shutil.which('yt-dlp')
    if not exe: return ''
    d=Path(tempfile.mkdtemp(dir=str(workdir)))
    try:
        subprocess.run([exe,'--skip-download','--write-subs','--write-auto-subs','--sub-langs',','.join(langs),'--sub-format','vtt','-o',str(d/'v.%(ext)s'),url],capture_output=True,timeout=300)
        files=sorted(d.glob('*.vtt'))
        return vtt_to_text(files[0].read_text(encoding='utf-8',errors='replace')) if files else ''
    finally:
        shutil.rmtree(d,ignore_errors=True)

def whisper_transcribe(path):
    p=Path(path)
    if not p.is_file(): raise ToolError(f'File not found: {p}')
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise ToolError('Local transcription needs faster-whisper: pip install faster-whisper') from e
    model=WhisperModel(os.environ.get('AES_WHISPER_MODEL','small'),device='auto',compute_type='default')
    segments,_=model.transcribe(str(p))
    return ' '.join(seg.text.strip() for seg in segments)
