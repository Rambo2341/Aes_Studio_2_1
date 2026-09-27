from __future__ import annotations
import json, os, sys, threading, time, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk

from .paths import APP_VERSION, DATA, WORKSPACE, MODELS, EXPORTS, IDENTITY_DATA
from .db import Database
from .model_runtime import RuntimeManager
from .security import PermissionManager
from .tools import ToolRegistry
from .agent import AgentEngine
from .knowledge import KnowledgeBase
from .evals import EvalRunner
from .training import TrainingLab
from .hub import AesHub
from .evolve import EvolutionManager

class C:
    BG='#050A11'; SIDE='#08111C'; CARD='#0B1622'; CARD2='#102235'; CARD3='#15304A'
    BORDER='#173A5B'; TEXT='#F2F8FF'; MUTED='#8297AE'; ACCENT='#008BFF'; ACCENT2='#00E5FF'
    GOOD='#50E3A4'; WARN='#F4C95D'; BAD='#FF687A'; INPUT='#07131F'

def clear(w):
    for c in w.winfo_children(): c.destroy()

class Card(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master,bg=C.CARD,highlightbackground=C.BORDER,highlightthickness=1,bd=0,**kw)

class AesStudio(tk.Tk):
    NAV=[
      ('chat','Chat','✦'),('projects','Projects','▦'),('models','Models','◈'),('knowledge','Knowledge','⌁'),
      ('memory','Memory','◎'),('skills','Skills','◆'),('tools','Tools & Permissions','⌘'),('evals','Evals','✓'),
      ('autopilot','Autopilot','☾'),('training','Training Lab','△'),('updates','Updates','↻'),('settings','Settings','⚙')]

    def __init__(self,db_path):
        super().__init__(); self.title(f'Aes Studio {APP_VERSION}'); self.configure(bg=C.BG)
        sw,sh=self.winfo_screenwidth(),self.winfo_screenheight(); ww=min(1500,max(1120,sw-70)); wh=min(920,max(720,sh-90))
        self.geometry(f'{ww}x{wh}+{max(0,(sw-ww)//2)}+{max(0,(sh-wh)//2)}'); self.minsize(1120,700)
        self.option_add('*Font',('Segoe UI',10)); self.protocol('WM_DELETE_WINDOW',self.on_close)
        self._images={}
        try:
            base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
            logo_path=base/'assets'/'aes.png'
            im=Image.open(logo_path).convert('RGBA')
            self._images['app']=ImageTk.PhotoImage(im.resize((64,64),Image.Resampling.LANCZOS))
            self._images['brand']=ImageTk.PhotoImage(im.resize((42,42),Image.Resampling.LANCZOS))
            self._images['rail']=ImageTk.PhotoImage(im.resize((34,34),Image.Resampling.LANCZOS))
            self.iconphoto(True,self._images['app'])
        except Exception:
            pass
        self.db=Database(db_path); self.runtimes=RuntimeManager(); self.permission=PermissionManager(self.db,self.ask_tool_permission)
        self.tools=ToolRegistry(WORKSPACE,self.db,self.permission); self.agent=AgentEngine(self.db,self.runtimes,self.tools)
        self.kb=KnowledgeBase(self.db); self.evals=EvalRunner(self.db,self.runtimes); self.training=TrainingLab(self.db,EXPORTS); self.evolver=EvolutionManager(self.db,self.runtimes,self.evals,self.training); self.hub=AesHub(self.db,self.runtimes,self.agent)
        self.current_cid=None; self.last_mid=None; self._sending=False; self.pages={}; self.nav_buttons={}; self.current_page='chat'; self._ttk(); self._shell(); self._build_pages(); self.refresh_all(); self.open_initial_chat(); self.show_page(self.db.setting('startup_page','chat'))

    def _ttk(self):
        s=ttk.Style(self)
        try:s.theme_use('clam')
        except Exception:pass
        s.configure('TCombobox',fieldbackground=C.INPUT,background=C.INPUT,foreground=C.TEXT,arrowcolor=C.MUTED,bordercolor=C.BORDER,lightcolor=C.BORDER,darkcolor=C.BORDER,padding=7)
        s.map('TCombobox',fieldbackground=[('readonly',C.INPUT)],foreground=[('readonly',C.TEXT)])
        s.configure('Treeview',background=C.CARD,fieldbackground=C.CARD,foreground=C.TEXT,rowheight=31,borderwidth=0)
        s.configure('Treeview.Heading',background=C.CARD2,foreground=C.MUTED,relief='flat',padding=(8,7))
        s.map('Treeview',background=[('selected',C.CARD3)],foreground=[('selected',C.TEXT)])
        s.configure('TCheckbutton',background=C.CARD,foreground=C.TEXT); s.map('TCheckbutton',background=[('active',C.CARD)])

    def _shell(self):
        self.rail=tk.Frame(self,bg='#04080E',width=58); self.rail.pack(side='left',fill='y'); self.rail.pack_propagate(False)
        top=tk.Frame(self.rail,bg='#04080E'); top.pack(fill='x',pady=(12,10))
        if self._images.get('rail'): tk.Label(top,image=self._images['rail'],bg='#04080E').pack()
        else: tk.Label(top,text='A',bg='#04080E',fg=C.ACCENT2,font=('Segoe UI',18,'bold')).pack()
        self.rail_buttons={}
        rail_items=[('chat','⌂'),('projects','▣'),('models','◇'),('knowledge','◫'),('memory','◉'),('skills','✦'),('tools','⌘')]
        for key,glyph in rail_items:
            b=tk.Button(self.rail,text=glyph,command=lambda k=key:self.show_page(k),bg='#04080E',fg=C.MUTED,activebackground=C.CARD2,activeforeground=C.ACCENT2,bd=0,relief='flat',cursor='hand2',font=('Segoe UI Symbol',14),pady=10)
            b.pack(fill='x',padx=7,pady=2); self.rail_buttons[key]=b
        tk.Frame(self.rail,bg=C.BORDER,height=1).pack(side='bottom',fill='x',padx=10,pady=(0,10))
        tk.Button(self.rail,text='⚙',command=lambda:self.show_page('settings'),bg='#04080E',fg=C.MUTED,activebackground=C.CARD2,activeforeground=C.TEXT,bd=0,font=('Segoe UI Symbol',13),pady=10).pack(side='bottom',fill='x',padx=7,pady=(0,8))

        self.sidebar=tk.Frame(self,bg=C.SIDE,width=230); self.sidebar.pack(side='left',fill='y'); self.sidebar.pack_propagate(False)
        brand=tk.Frame(self.sidebar,bg=C.SIDE); brand.pack(fill='x',padx=14,pady=(15,11))
        if self._images.get('brand'): tk.Label(brand,image=self._images['brand'],bg=C.SIDE).pack(side='left')
        bt=tk.Frame(brand,bg=C.SIDE); bt.pack(side='left',padx=9)
        tk.Label(bt,text='Aes Studio',bg=C.SIDE,fg=C.TEXT,font=('Segoe UI',15,'bold')).pack(anchor='w')
        tk.Label(bt,text=f'Your AI Agent • {APP_VERSION}',bg=C.SIDE,fg=C.ACCENT2,font=('Segoe UI',8)).pack(anchor='w')
        self.button(self.sidebar,'＋  محادثة جديدة / New chat',self.new_chat,accent=True).pack(fill='x',padx=12,pady=(0,12))
        tk.Label(self.sidebar,text='WORKSPACE',bg=C.SIDE,fg='#55708B',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=16,pady=(1,4))
        nav=tk.Frame(self.sidebar,bg=C.SIDE); nav.pack(fill='both',expand=True,padx=8)
        for key,label,glyph in self.NAV:
            b=tk.Button(nav,text=f'  {glyph}    {label}',anchor='w',bg=C.SIDE,fg=C.MUTED,activebackground=C.CARD2,activeforeground=C.TEXT,bd=0,relief='flat',cursor='hand2',padx=10,pady=8,command=lambda k=key:self.show_page(k))
            b.pack(fill='x',pady=1); self.nav_buttons[key]=b
        foot=tk.Frame(self.sidebar,bg=C.SIDE); foot.pack(side='bottom',fill='x',padx=14,pady=13)
        tk.Frame(foot,bg=C.BORDER,height=1).pack(fill='x',pady=(0,9))
        self.side_model=tk.Label(foot,text='Model: —',bg=C.SIDE,fg=C.MUTED,font=('Segoe UI',8),anchor='w'); self.side_model.pack(fill='x')
        self.side_status=tk.Label(foot,text='●  Agent ready',bg=C.SIDE,fg=C.GOOD,font=('Segoe UI',8),anchor='w'); self.side_status.pack(fill='x',pady=(4,0))
        self.content=tk.Frame(self,bg=C.BG); self.content.pack(side='left',fill='both',expand=True)
    def _build_pages(self):
        for key,_,_ in self.NAV:self.pages[key]=tk.Frame(self.content,bg=C.BG)
        self.build_chat(self.pages['chat']); self.build_projects(self.pages['projects']); self.build_models(self.pages['models']); self.build_knowledge(self.pages['knowledge']); self.build_memory(self.pages['memory']); self.build_skills(self.pages['skills']); self.build_tools(self.pages['tools']); self.build_evals(self.pages['evals']); self.build_autopilot(self.pages['autopilot']); self.build_training(self.pages['training']); self.build_updates(self.pages['updates']); self.build_settings(self.pages['settings'])

    def header(self,parent,title,sub,right=None):
        row=tk.Frame(parent,bg=C.BG); row.pack(fill='x',padx=28,pady=(24,14)); left=tk.Frame(row,bg=C.BG); left.pack(side='left',fill='x',expand=True)
        tk.Label(left,text=title,bg=C.BG,fg=C.TEXT,font=('Segoe UI',22,'bold')).pack(anchor='w'); tk.Label(left,text=sub,bg=C.BG,fg=C.MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(3,0))
        if right:right(row).pack(side='right')
        return row
    def button(self,m,text,cmd,accent=False,danger=False):
        bg=C.ACCENT if accent else ('#41222B' if danger else C.CARD2); act='#66B4FF' if accent else ('#5A2B36' if danger else C.CARD3)
        return tk.Button(m,text=text,command=cmd,bg=bg,fg='white' if accent or danger else C.TEXT,activebackground=act,activeforeground='white',bd=0,relief='flat',cursor='hand2',font=('Segoe UI',9,'bold'),padx=12,pady=7)
    def entry(self,m,var=None,show=None): return tk.Entry(m,textvariable=var,show=show,bg=C.INPUT,fg=C.TEXT,insertbackground=C.TEXT,relief='flat',bd=0,highlightthickness=1,highlightbackground=C.BORDER,highlightcolor=C.ACCENT,font=('Segoe UI',10))
    def text(self,m,height=8): return tk.Text(m,height=height,bg=C.INPUT,fg=C.TEXT,insertbackground=C.TEXT,selectbackground=C.ACCENT,wrap='word',relief='flat',bd=0,highlightthickness=1,highlightbackground=C.BORDER,highlightcolor=C.ACCENT,padx=11,pady=9,font=('Segoe UI',10),undo=True)
    def label_field(self,m,label,widget):
        box=tk.Frame(m,bg=C.CARD); box.pack(fill='x',pady=5); tk.Label(box,text=label,bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w',pady=(0,4)); widget.pack(fill='x',ipady=6); return widget

    def show_page(self,key):
        if key not in self.pages:key='chat'
        self.current_page=key
        for p in self.pages.values():p.pack_forget()
        self.pages[key].pack(fill='both',expand=True)
        for k,b in self.nav_buttons.items():b.configure(bg=C.CARD2 if k==key else C.SIDE,fg=C.TEXT if k==key else C.MUTED)
        for k,b in getattr(self,'rail_buttons',{}).items():b.configure(bg=C.CARD2 if k==key else '#04080E',fg=C.ACCENT2 if k==key else C.MUTED)
        getattr(self,f'refresh_{key}',lambda:None)()

    # CHAT
    def build_chat(self,page):
        outer=tk.Frame(page,bg=C.BG); outer.pack(fill='both',expand=True,padx=14,pady=14)

        left=Card(outer,width=245); left.pack(side='left',fill='y',padx=(0,10)); left.pack_propagate(False)
        hh=tk.Frame(left,bg=C.CARD); hh.pack(fill='x',padx=13,pady=(14,8))
        tk.Label(hh,text='المحادثات  Conversations',bg=C.CARD,fg=C.TEXT,font=('Segoe UI',10,'bold')).pack(side='left')
        self.chat_count=tk.Label(hh,text='0',bg=C.CARD2,fg=C.ACCENT2,font=('Segoe UI',8,'bold'),padx=7,pady=2); self.chat_count.pack(side='right')
        self.chat_search=tk.StringVar(); e=self.entry(left,self.chat_search); e.pack(fill='x',padx=12,ipady=6); self.chat_search.trace_add('write',lambda *_:self.refresh_chat())
        self.conv_list=tk.Listbox(left,bg=C.CARD,fg=C.TEXT,selectbackground='#12385B',selectforeground=C.TEXT,activestyle='none',bd=0,highlightthickness=0,font=('Segoe UI',9)); self.conv_list.pack(fill='both',expand=True,padx=7,pady=9); self.conv_list.bind('<<ListboxSelect>>',self.load_selected_chat)
        ar=tk.Frame(left,bg=C.CARD); ar.pack(fill='x',padx=9,pady=(0,9)); self.button(ar,'Rename',self.rename_chat).pack(side='left'); self.button(ar,'Delete',self.delete_chat,danger=True).pack(side='right')

        center=tk.Frame(outer,bg=C.BG); center.pack(side='left',fill='both',expand=True)
        bar=Card(center,height=58); bar.pack(fill='x',pady=(0,9)); bar.pack_propagate(False)
        tk.Label(bar,text='◈',bg=C.CARD,fg=C.ACCENT2,font=('Segoe UI Symbol',14,'bold')).pack(side='left',padx=(13,7))
        self.chat_project=tk.StringVar(value='No project'); self.chat_project_box=ttk.Combobox(bar,textvariable=self.chat_project,state='readonly',width=18); self.chat_project_box.pack(side='left',pady=10)
        self.chat_mode=tk.StringVar(value='Agent'); ttk.Combobox(bar,textvariable=self.chat_mode,state='readonly',values=['Agent','Code + Review','Plan','Research'],width=13).pack(side='left',padx=7)
        self.chat_model=tk.StringVar(); self.chat_model_box=ttk.Combobox(bar,textvariable=self.chat_model,state='readonly',width=18); self.chat_model_box.pack(side='right',padx=(7,12),pady=10); self.chat_model_box.bind('<<ComboboxSelected>>',lambda e:self.on_model_change())
        self.permission_mode_var=tk.StringVar(value={'ask':'Ask','auto':'Auto','full':'Full access'}.get(self.db.setting('permission_mode','ask'),'Ask'))
        trust=ttk.Combobox(bar,textvariable=self.permission_mode_var,state='readonly',values=['Ask','Auto','Full access'],width=12); trust.pack(side='right',pady=10); trust.bind('<<ComboboxSelected>>',lambda e:self.on_permission_mode_change())
        self.local_badge=tk.Label(bar,text='● AGENT ACTIVE',bg='#0C2C24',fg=C.GOOD,font=('Segoe UI',8,'bold'),padx=9,pady=4); self.local_badge.pack(side='right',padx=8)

        cc=Card(center); cc.pack(fill='both',expand=True)
        self.chat_view=tk.Text(cc,bg=C.CARD,fg=C.TEXT,relief='flat',bd=0,wrap='word',state='disabled',padx=22,pady=18,selectbackground=C.ACCENT,font=('Segoe UI',10)); sb=tk.Scrollbar(cc,command=self.chat_view.yview,bg=C.CARD,troughcolor=C.CARD,relief='flat'); self.chat_view.configure(yscrollcommand=sb.set); sb.pack(side='right',fill='y'); self.chat_view.pack(fill='both',expand=True)
        self.chat_view.tag_configure('you',foreground='#79BFFF',font=('Segoe UI',9,'bold'),spacing1=10); self.chat_view.tag_configure('aes',foreground=C.ACCENT2,font=('Segoe UI',9,'bold'),spacing1=10); self.chat_view.tag_configure('body',foreground=C.TEXT,font=('Segoe UI',10),spacing3=12); self.chat_view.tag_configure('tool',foreground=C.GOOD,font=('Consolas',9),lmargin1=14,lmargin2=14,spacing3=7); self.chat_view.tag_configure('empty',foreground=C.MUTED,font=('Segoe UI',11),justify='center',spacing1=110)

        comp=Card(center,height=132); comp.pack(fill='x',pady=(9,0)); comp.pack_propagate(False)
        self.prompt=tk.Text(comp,bg=C.INPUT,fg=C.TEXT,insertbackground=C.TEXT,relief='flat',bd=0,wrap='word',padx=13,pady=11,font=('Segoe UI',10),undo=True); self.prompt.pack(fill='both',expand=True,padx=8,pady=(8,2)); self.prompt.bind('<Control-Return>',lambda e:(self.send_chat(),'break')[1])
        bottom=tk.Frame(comp,bg=C.CARD); bottom.pack(fill='x',padx=8,pady=(2,8))
        tk.Button(bottom,text='＋',command=lambda:self.show_page('knowledge'),bg=C.CARD2,fg=C.TEXT,bd=0,padx=10,pady=5,cursor='hand2').pack(side='left')
        tk.Button(bottom,text='◉ Web / Research',command=lambda:self.chat_mode.set('Research'),bg=C.CARD2,fg=C.TEXT,bd=0,padx=10,pady=5,cursor='hand2').pack(side='left',padx=5)
        tk.Button(bottom,text='⌘ Tools',command=lambda:self.show_page('tools'),bg=C.CARD2,fg=C.TEXT,bd=0,padx=10,pady=5,cursor='hand2').pack(side='left')
        self.send_btn=self.button(bottom,'Send  ➜',self.send_chat,accent=True); self.send_btn.pack(side='right')
        tk.Label(bottom,text='Ctrl + Enter',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(side='right',padx=10)

        util=Card(outer,width=290); util.pack(side='left',fill='y',padx=(10,0)); util.pack_propagate(False)
        tabs=tk.Frame(util,bg=C.CARD); tabs.pack(fill='x',padx=10,pady=(11,8))
        tk.Label(tabs,text='Outputs',bg=C.CARD2,fg=C.ACCENT2,font=('Segoe UI',9,'bold'),padx=10,pady=6).pack(side='left')
        tk.Label(tabs,text='Sources',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',9),padx=10,pady=6).pack(side='left')
        tk.Label(tabs,text='Skills',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',9),padx=10,pady=6).pack(side='left')
        tk.Label(util,text='AGENT CONTEXT',bg=C.CARD,fg='#55708B',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=13,pady=(4,3))
        self.context_summary=tk.Text(util,height=10,bg=C.INPUT,fg=C.TEXT,relief='flat',bd=0,wrap='word',state='disabled',padx=10,pady=8,font=('Segoe UI',9)); self.context_summary.pack(fill='x',padx=10)
        tk.Label(util,text='RECENT TOOL ACTIVITY',bg=C.CARD,fg='#55708B',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=13,pady=(12,3))
        self.tool_activity=tk.Text(util,height=10,bg=C.INPUT,fg=C.GOOD,relief='flat',bd=0,wrap='word',state='disabled',padx=10,pady=8,font=('Consolas',8)); self.tool_activity.pack(fill='both',expand=True,padx=10,pady=(0,9))
        fb=tk.Frame(util,bg=C.CARD); fb.pack(fill='x',padx=10,pady=(0,10)); tk.Label(fb,text='Teach Aes:',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(side='left'); tk.Button(fb,text='👍',command=lambda:self.rate(1),bg=C.CARD2,fg=C.GOOD,bd=0,padx=8,pady=4).pack(side='left',padx=5); tk.Button(fb,text='👎',command=lambda:self.rate(-1),bg=C.CARD2,fg=C.BAD,bd=0,padx=8,pady=4).pack(side='left')
    def on_permission_mode_change(self):
        mapping={'Ask':'ask','Auto':'auto','Full access':'full'}
        mode=mapping.get(self.permission_mode_var.get(),'ask'); self.db.set_setting('permission_mode',mode)
        label={'ask':'Permission: Ask','auto':'Permission: Auto','full':'Permission: Full access'}[mode]
        self.side_status.configure(text='●  '+label,fg=C.WARN if mode=='ask' else C.GOOD)

    def refresh_chat_context_panel(self):
        if not hasattr(self,'context_summary'): return
        try:
            docs=len(self.db.docs()); skills=self.db.enabled_skills(); memories=len(self.db.memories()); tasks=self.db.tasks()
            identity_ok=sum(1 for n in ('SOUL.md','IDENTITY.md','USER.md') if (IDENTITY_DATA/n).exists())
            txt=(f"Aes {APP_VERSION}\n"
                 f"Identity files: {identity_ok}/3\n"
                 f"Memory entries: {memories}\nKnowledge docs: {docs}\n"
                 f"Enabled skills: {len(skills)}\nTasks: {len(tasks)}\n"
                 f"Trust mode: {self.db.setting('permission_mode','ask').upper()}\n\n"
                 "AGENT loop\nAim → Identity → Equip → Narrow → Trust")
            self.context_summary.configure(state='normal'); self.context_summary.delete('1.0','end'); self.context_summary.insert('1.0',txt); self.context_summary.configure(state='disabled')
            traces=[]
            if self.current_cid:
                for m in reversed(list(self.db.messages(self.current_cid))):
                    if m['role']!='assistant': continue
                    try: meta=json.loads(m['meta_json'] or '{}')
                    except Exception: meta={}
                    traces=meta.get('tool_traces',[]) or []
                    if traces: break
            lines=[f"✓ {t.get('tool')}  {str(t.get('arguments') or '')[:110]}" for t in traces[-10:]] or ['No tool calls yet.']
            self.tool_activity.configure(state='normal'); self.tool_activity.delete('1.0','end'); self.tool_activity.insert('1.0','\n'.join(lines)); self.tool_activity.configure(state='disabled')
        except Exception:
            pass

    def open_initial_chat(self):
        rows=self.db.conversations(); self.current_cid=rows[0]['id'] if rows else self.db.new_conversation(model_name=self.db.setting('default_model','Aes 2.1 Local')); self.render_chat()
    def new_chat(self):
        self.current_cid=self.db.new_conversation(model_name=self.chat_model.get() or self.db.setting('default_model','Aes 2.1 Local')); self.last_mid=None; self.refresh_chat(); self.render_chat(); self.show_page('chat'); self.prompt.focus_set()
    def refresh_chat(self):
        if not hasattr(self,'conv_list'):return
        self._conv_rows=self.db.conversations(self.chat_search.get().strip()); self.conv_list.delete(0,'end')
        for r in self._conv_rows:self.conv_list.insert('end','  '+(r['title'][:38]+'…' if len(r['title'])>39 else r['title']))
        self.chat_count.configure(text=str(len(self._conv_rows)))
    def load_selected_chat(self,_=None):
        s=self.conv_list.curselection()
        if s:self.current_cid=self._conv_rows[s[0]]['id']; self.render_chat()
    def render_chat(self):
        if not self.current_cid:return
        rows=self.db.messages(self.current_cid); self.chat_view.configure(state='normal'); self.chat_view.delete('1.0','end'); self.last_mid=None
        if not rows:self.chat_view.insert('end','Aes is ready. Choose a local model, project and mode, then give it a task.','empty')
        for m in rows:
            self.chat_view.insert('end',('YOU\n' if m['role']=='user' else 'AES\n'),'you' if m['role']=='user' else 'aes'); self.chat_view.insert('end',m['content'].strip()+'\n','body')
            if m['role']=='assistant':
                self.last_mid=m['id']
                try: meta=json.loads(m['meta_json'] or '{}')
                except Exception: meta={}
                for t in meta.get('tool_traces',[]):self.chat_view.insert('end',f"↳ {t.get('tool')}  {str(t.get('arguments'))[:160]}\n",'tool')
        self.chat_view.configure(state='disabled'); self.chat_view.see('end'); self.refresh_chat_context_panel()
    def _project_id_by_name(self,name):
        for r in self.db.projects():
            if r['name']==name:return r['id']
        return None
    def send_chat(self):
        text=self.prompt.get('1.0','end').strip(); model=self.chat_model.get().strip()
        if not text or self._sending:return
        if not model:messagebox.showwarning('Aes','Choose a model profile.');return
        if not self.current_cid:self.new_chat()
        # Lightweight slash workflows inspired by modern coding-agent CLIs.
        low=text.lower().strip()
        if low=='/memory': self.prompt.delete('1.0','end'); self.show_page('memory'); return
        if low=='/skills': self.prompt.delete('1.0','end'); self.show_page('skills'); return
        pid=self._project_id_by_name(self.chat_project.get())
        project=next((r for r in self.db.projects() if r['id']==pid),None)
        if project: self.tools.set_workspace(project['path'])
        if low in ('/diff','/tasks'):
            self.prompt.delete('1.0','end')
            self.db.add_message(self.current_cid,'user',text)
            try:
                result=self.tools.call('git_diff' if low=='/diff' else 'task_list',{})
            except Exception as e: result=f'ERROR: {e}'
            self.db.add_message(self.current_cid,'assistant',result,{'slash_command':low})
            self.refresh_chat(); self.render_chat(); return
        mode=self.chat_mode.get()
        for prefix,target in [('/plan ','Plan'),('/code ','Code + Review'),('/research ','Research')]:
            if low.startswith(prefix):
                text=text[len(prefix):].strip(); mode=target; break
        self._sending=True; self.send_btn.configure(text='Working…',state='disabled'); self.prompt.delete('1.0','end'); cid=self.current_cid
        self.side_status.configure(text='●  Aes is working',fg=C.WARN)
        def work():
            try:
                if mode=='Code + Review':ans,mid,tr=self.agent.coordinated_code(cid,model,text,pid)
                else:
                    mm={'Agent':'agent','Plan':'plan','Research':'research'}.get(mode,'agent'); ans,mid,tr=self.agent.run(cid,model,text,mm,pid)
                self.after(0,lambda:self.send_done(None))
            except Exception as e:self.after(0,lambda:self.send_done(e))
        threading.Thread(target=work,daemon=True).start(); self.render_chat()
    def send_done(self,err):
        self._sending=False; self.send_btn.configure(text='Send  →',state='normal'); self.side_status.configure(text='●  Local core ready',fg=C.GOOD)
        if err:messagebox.showerror('Aes error',str(err))
        self.refresh_chat(); self.render_chat(); self.refresh_chat_context_panel()
    def rename_chat(self):
        if not self.current_cid:return
        x=simpledialog.askstring('Rename','Conversation title:',parent=self)
        if x:self.db.rename_conversation(self.current_cid,x[:80]);self.refresh_chat()
    def delete_chat(self):
        if self.current_cid and messagebox.askyesno('Delete','Delete this conversation?',parent=self):self.db.delete_conversation(self.current_cid);self.current_cid=None;self.open_initial_chat();self.refresh_chat()
    def rate(self,rating):
        if not self.last_mid:messagebox.showinfo('Aes','No assistant answer to rate.');return
        note=simpledialog.askstring('Feedback','Optional note for Aes training:',parent=self) or ''; self.db.add_feedback(self.current_cid,self.last_mid,rating,note); self.side_status.configure(text='●  Feedback saved',fg=C.GOOD)
        model=self.chat_model.get() or self.db.setting('default_model','Aes 2.1 Local')
        def evolve_work():
            try:
                result=self.evolver.maybe_stage(model)
                if result:self.after(0,lambda: self.side_status.configure(text='●  New Aes improvement candidate staged',fg=C.GOOD))
            except Exception as e:
                self.db.log('auto_evolve',str(e),False)
        threading.Thread(target=evolve_work,daemon=True).start()
    def on_model_change(self):self.db.set_setting('default_model',self.chat_model.get());self.side_model.configure(text='Model: '+self.chat_model.get())

    # PROJECTS
    def build_projects(self,page):
        self.header(page,'Projects','Give Aes isolated workspaces and project-specific instructions.')
        body=tk.Frame(page,bg=C.BG); body.pack(fill='both',expand=True,padx=28,pady=(0,25)); left=Card(body,width=330);left.pack(side='left',fill='y',padx=(0,13));left.pack_propagate(False); self.project_list=tk.Listbox(left,bg=C.CARD,fg=C.TEXT,selectbackground=C.CARD3,bd=0,highlightthickness=0);self.project_list.pack(fill='both',expand=True,padx=9,pady=10);self.project_list.bind('<<ListboxSelect>>',self.load_project); row=tk.Frame(left,bg=C.CARD);row.pack(fill='x',padx=9,pady=9);self.button(row,'+ New',self.new_project).pack(side='left');self.button(row,'Delete',self.delete_project,danger=True).pack(side='right')
        form=Card(body);form.pack(side='left',fill='both',expand=True);inn=tk.Frame(form,bg=C.CARD);inn.pack(fill='both',expand=True,padx=20,pady=18);self.proj_name=tk.StringVar();self.proj_path=tk.StringVar();self.label_field(inn,'PROJECT NAME',self.entry(inn,self.proj_name)); pathrow=tk.Frame(inn,bg=C.CARD);pathrow.pack(fill='x',pady=5);tk.Label(pathrow,text='WORKSPACE FOLDER',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');pr=tk.Frame(pathrow,bg=C.CARD);pr.pack(fill='x');e=self.entry(pr,self.proj_path);e.pack(side='left',fill='x',expand=True,ipady=6);self.button(pr,'Browse',self.browse_project).pack(side='right',padx=(7,0));tk.Label(inn,text='PROJECT INSTRUCTIONS',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w',pady=(10,4));self.proj_inst=self.text(inn,14);self.proj_inst.pack(fill='both',expand=True);self.button(inn,'Save project',self.save_project,accent=True).pack(anchor='e',pady=(12,0));self._project_selected=None
    def refresh_projects(self):
        if not hasattr(self,'project_list'):return
        self._projects=self.db.projects();self.project_list.delete(0,'end');[self.project_list.insert('end','  '+r['name']) for r in self._projects];self.refresh_project_choices()
    def new_project(self):self._project_selected=None;self.proj_name.set('');self.proj_path.set(str(WORKSPACE));self.proj_inst.delete('1.0','end')
    def browse_project(self):
        p=filedialog.askdirectory(parent=self)
        if p:self.proj_path.set(p)
    def load_project(self,_=None):
        s=self.project_list.curselection()
        if not s:return
        r=self._projects[s[0]];self._project_selected=r['id'];self.proj_name.set(r['name']);self.proj_path.set(r['path']);self.proj_inst.delete('1.0','end');self.proj_inst.insert('1.0',r['instructions'])
    def save_project(self):
        n=self.proj_name.get().strip();p=self.proj_path.get().strip()
        if not n or not p:messagebox.showwarning('Aes','Name and folder are required.');return
        Path(p).expanduser().mkdir(parents=True,exist_ok=True);self._project_selected=self.db.save_project(n,str(Path(p).expanduser().resolve()),self.proj_inst.get('1.0','end').strip(),self._project_selected);self.refresh_projects()
    def delete_project(self):
        if self._project_selected and messagebox.askyesno('Delete','Delete this project entry? Files are not deleted.',parent=self):self.db.delete_project(self._project_selected);self.new_project();self.refresh_projects()
    def refresh_project_choices(self):
        if hasattr(self,'chat_project_box'):
            vals=['No project']+[r['name'] for r in self.db.projects()];self.chat_project_box.configure(values=vals)
            if self.chat_project.get() not in vals:self.chat_project.set('No project')

    # MODELS
    def build_models(self,page):
        self.header(page,'Models','Choose the brain: local GGUF, Ollama / LM Studio / DeepSeek (openai_compat) or Claude (anthropic). Keys may be written as env:VARIABLE.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));left=Card(body,width=320);left.pack(side='left',fill='y',padx=(0,13));left.pack_propagate(False);self.model_list=tk.Listbox(left,bg=C.CARD,fg=C.TEXT,selectbackground=C.CARD3,bd=0,highlightthickness=0);self.model_list.pack(fill='both',expand=True,padx=9,pady=10);self.model_list.bind('<<ListboxSelect>>',self.load_model);rr=tk.Frame(left,bg=C.CARD);rr.pack(fill='x',padx=9,pady=9);self.button(rr,'+ New',self.new_model).pack(side='left');self.button(rr,'Delete',self.delete_model,danger=True).pack(side='right')
        form=Card(body);form.pack(side='left',fill='both',expand=True);inn=tk.Frame(form,bg=C.CARD);inn.pack(fill='both',expand=True,padx=19,pady=16);self.mvars={k:tk.StringVar() for k in ['name','runtime','path','ctx','gpu','temp','max','endpoint','api_key']};self.label_field(inn,'AES MODEL PROFILE',self.entry(inn,self.mvars['name']));row=tk.Frame(inn,bg=C.CARD);row.pack(fill='x',pady=5);lf=tk.Frame(row,bg=C.CARD);lf.pack(side='left',fill='x',expand=True,padx=(0,6));tk.Label(lf,text='RUNTIME',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');ttk.Combobox(lf,textvariable=self.mvars['runtime'],state='readonly',values=['demo','llama_cpp','openai_compat','anthropic']).pack(fill='x');rf=tk.Frame(row,bg=C.CARD);rf.pack(side='left',fill='x',expand=True);tk.Label(rf,text='CONTEXT TOKENS',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');self.entry(rf,self.mvars['ctx']).pack(fill='x',ipady=6)
        pr=tk.Frame(inn,bg=C.CARD);pr.pack(fill='x',pady=6);tk.Label(pr,text='GGUF FILE (llama_cpp)  /  MODEL ID (openai_compat, anthropic)',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');r2=tk.Frame(pr,bg=C.CARD);r2.pack(fill='x');self.entry(r2,self.mvars['path']).pack(side='left',fill='x',expand=True,ipady=6);self.button(r2,'Browse .gguf',self.browse_model).pack(side='right',padx=(7,0))
        er=tk.Frame(inn,bg=C.CARD);er.pack(fill='x',pady=5)
        for i,(lab,k,show) in enumerate([('ENDPOINT URL (openai_compat)','endpoint',None),('API KEY  (or env:NAME)','api_key','•')]):
            f=tk.Frame(er,bg=C.CARD);f.pack(side='left',fill='x',expand=True,padx=(0 if i==0 else 5,0));tk.Label(f,text=lab,bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');self.entry(f,self.mvars[k],show=show).pack(fill='x',ipady=6)
        nums=tk.Frame(inn,bg=C.CARD);nums.pack(fill='x',pady=5)
        for i,(lab,k) in enumerate([('GPU LAYERS','gpu'),('TEMPERATURE','temp'),('MAX OUTPUT','max')]):
            f=tk.Frame(nums,bg=C.CARD);f.pack(side='left',fill='x',expand=True,padx=(0 if i==0 else 5,0));tk.Label(f,text=lab,bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');self.entry(f,self.mvars[k]).pack(fill='x',ipady=6)
        tk.Label(inn,text='SYSTEM / IDENTITY PROMPT',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w',pady=(10,4));self.model_prompt=self.text(inn,12);self.model_prompt.pack(fill='both',expand=True);act=tk.Frame(inn,bg=C.CARD);act.pack(fill='x',pady=(12,0));self.button(act,'Save',self.save_model,accent=True).pack(side='left');self.button(act,'Test model',self.test_model).pack(side='left',padx=7);self.button(act,'Set default',self.set_default_model).pack(side='right');self._model_selected=None
    def refresh_models(self):
        if not hasattr(self,'model_list'):return
        self._models=self.db.models();self.model_list.delete(0,'end');[self.model_list.insert('end','  '+r['name']+'  • '+{'llama_cpp':'local','openai_compat':'server','anthropic':'claude'}.get(r['runtime'],'demo')) for r in self._models];names=[r['name'] for r in self._models];self.chat_model_box.configure(values=names);default=self.db.setting('default_model','Aes 2.1 Local');self.chat_model.set(default if default in names else (names[0] if names else ''));self.side_model.configure(text='Model: '+(self.chat_model.get() or '—'))
    def new_model(self):self._model_selected=None;[self.mvars[k].set(v) for k,v in {'name':'Aes Custom','runtime':'openai_compat','path':'','ctx':'32768','gpu':'-1','temp':'0.2','max':'4096','endpoint':'http://127.0.0.1:11434/v1','api_key':''}.items()];self.model_prompt.delete('1.0','end')
    def load_model(self,_=None):
        s=self.model_list.curselection()
        if not s:return
        r=self._models[s[0]];self._model_selected=r['name'];vals={'name':r['name'],'runtime':r['runtime'],'path':r['model_path'],'ctx':r['context_size'],'gpu':r['gpu_layers'],'temp':r['temperature'],'max':r['max_tokens'],'endpoint':r['endpoint'],'api_key':r['api_key']};[self.mvars[k].set(str(v)) for k,v in vals.items()];self.model_prompt.delete('1.0','end');self.model_prompt.insert('1.0',r['system_prompt'])
    def browse_model(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[('GGUF models','*.gguf'),('All files','*.*')]);
        if p:self.mvars['path'].set(p)
    def save_model(self):
        try:self.db.save_model(self.mvars['name'].get().strip(),self.mvars['runtime'].get(),self.mvars['path'].get().strip(),int(self.mvars['ctx'].get()),int(self.mvars['gpu'].get()),float(self.mvars['temp'].get()),int(self.mvars['max'].get()),self.model_prompt.get('1.0','end').strip(),1,self.mvars['endpoint'].get().strip(),self.mvars['api_key'].get().strip());self.runtimes.unload(self._model_selected);self._model_selected=self.mvars['name'].get().strip();self.refresh_models()
        except Exception as e:messagebox.showerror('Model',str(e))
    def delete_model(self):
        if self._model_selected and messagebox.askyesno('Delete','Delete this model profile? The GGUF file is not deleted.',parent=self):self.db.delete_model(self._model_selected);self.runtimes.unload(self._model_selected);self._model_selected=None;self.refresh_models()
    def test_model(self):
        try:r=self.db.model(self.mvars['name'].get().strip()) or self.db.model(self._model_selected);ans=self.runtimes.complete(r,[{'role':'user','content':'Reply exactly: Aes model ready.'}]);messagebox.showinfo('Model test',ans[:1000])
        except Exception as e:messagebox.showerror('Model test',str(e))
    def set_default_model(self):
        n=self.mvars['name'].get().strip()
        if n:self.db.set_setting('default_model',n);self.chat_model.set(n);self.on_model_change()

    # KNOWLEDGE
    def build_knowledge(self,page):
        self.header(page,'Knowledge','Import books, documentation, source code and notes into Aes private retrieval memory.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));left=Card(body,width=480);left.pack(side='left',fill='both',expand=False,padx=(0,13));self.doc_tree=ttk.Treeview(left,columns=('chars',),show='tree headings');self.doc_tree.heading('#0',text='Document');self.doc_tree.heading('chars',text='Characters');self.doc_tree.column('#0',width=330);self.doc_tree.column('chars',width=100,anchor='e');self.doc_tree.pack(fill='both',expand=True,padx=9,pady=9);r=tk.Frame(left,bg=C.CARD);r.pack(fill='x',padx=9,pady=9);self.button(r,'Import files',self.import_knowledge,accent=True).pack(side='left');self.button(r,'Delete',self.delete_knowledge,danger=True).pack(side='right')
        right=Card(body);right.pack(side='left',fill='both',expand=True);inn=tk.Frame(right,bg=C.CARD);inn.pack(fill='both',expand=True,padx=17,pady=16);tk.Label(inn,text='Search Aes knowledge',bg=C.CARD,fg=C.TEXT,font=('Segoe UI',11,'bold')).pack(anchor='w');self.know_query=tk.StringVar();e=self.entry(inn,self.know_query);e.pack(fill='x',ipady=7,pady=8);e.bind('<Return>',lambda _:self.search_knowledge());self.button(inn,'Search',self.search_knowledge).pack(anchor='e');self.know_results=self.text(inn,20);self.know_results.pack(fill='both',expand=True,pady=(10,0))
    def refresh_knowledge(self):
        if not hasattr(self,'doc_tree'):return
        self.doc_tree.delete(*self.doc_tree.get_children());
        for r in self.db.docs():self.doc_tree.insert('', 'end', iid=str(r['id']), text=r['name'], values=(f"{r['chars']:,}",))
    def import_knowledge(self):
        paths=filedialog.askopenfilenames(parent=self,title='Import knowledge')
        if not paths:return
        ok=0;errs=[]
        for p in paths:
            try:self.kb.import_file(p);ok+=1
            except Exception as e:errs.append(f'{Path(p).name}: {e}')
        self.refresh_knowledge();messagebox.showinfo('Knowledge',f'Imported {ok} file(s).'+(('\n\n'+ '\n'.join(errs[:6])) if errs else ''))
    def delete_knowledge(self):
        sel=self.doc_tree.selection()
        if sel and messagebox.askyesno('Delete','Remove selected knowledge document?',parent=self):self.db.delete_doc(int(sel[0]));self.refresh_knowledge()
    def search_knowledge(self):
        rows=self.kb.search(self.know_query.get(),8);self.know_results.delete('1.0','end')
        for r in rows:self.know_results.insert('end',f"[{r['name']}]\n{r['content'][:1600]}\n\n")

    # MEMORY
    def build_memory(self,page):
        self.header(page,'Memory','Persistent owner-controlled memory. Aes retrieves only relevant items during a task.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));left=Card(body,width=500);left.pack(side='left',fill='both',padx=(0,13));left.pack_propagate(False);self.mem_search=tk.StringVar();e=self.entry(left,self.mem_search);e.pack(fill='x',padx=12,pady=(12,6),ipady=6);self.mem_search.trace_add('write',lambda *_:self.refresh_memory());self.mem_list=tk.Listbox(left,bg=C.CARD,fg=C.TEXT,selectbackground=C.CARD3,bd=0,highlightthickness=0);self.mem_list.pack(fill='both',expand=True,padx=8,pady=7);self.mem_list.bind('<<ListboxSelect>>',self.load_memory)
        right=Card(body);right.pack(side='left',fill='both',expand=True);inn=tk.Frame(right,bg=C.CARD);inn.pack(fill='both',expand=True,padx=18,pady=17);self.mem_text=self.text(inn,12);self.mem_text.pack(fill='both',expand=True);self.mem_tags=tk.StringVar();self.mem_kind=tk.StringVar(value='fact');self.mem_importance=tk.StringVar(value='2');self.label_field(inn,'TAGS',self.entry(inn,self.mem_tags));row=tk.Frame(inn,bg=C.CARD);row.pack(fill='x',pady=5);ttk.Combobox(row,textvariable=self.mem_kind,state='readonly',values=['fact','preference','project','procedure','lesson']).pack(side='left',fill='x',expand=True);ttk.Combobox(row,textvariable=self.mem_importance,state='readonly',values=['1','2','3','4','5']).pack(side='left',fill='x',expand=True,padx=(7,0));act=tk.Frame(inn,bg=C.CARD);act.pack(fill='x',pady=8);self.button(act,'New',self.new_memory).pack(side='left');self.button(act,'Save',self.save_memory,accent=True).pack(side='left',padx=7);self.button(act,'Delete',self.delete_memory,danger=True).pack(side='right');self._mem_id=None
    def refresh_memory(self):
        if not hasattr(self,'mem_list'):return
        self._mem_rows=self.db.memories(self.mem_search.get().strip());self.mem_list.delete(0,'end');[self.mem_list.insert('end',f"  {'★'*int(r['importance'])}  {r['text'][:65].replace(chr(10),' ')}") for r in self._mem_rows]
    def load_memory(self,_=None):
        s=self.mem_list.curselection()
        if not s:return
        r=self._mem_rows[s[0]];self._mem_id=r['id'];self.mem_text.delete('1.0','end');self.mem_text.insert('1.0',r['text']);self.mem_tags.set(r['tags']);self.mem_kind.set(r['kind']);self.mem_importance.set(str(r['importance']))
    def new_memory(self):self._mem_id=None;self.mem_text.delete('1.0','end');self.mem_tags.set('');self.mem_kind.set('fact');self.mem_importance.set('2')
    def save_memory(self):
        txt=self.mem_text.get('1.0','end').strip()
        if not txt:return
        if self._mem_id:self.db.update_memory(self._mem_id,txt,self.mem_tags.get(),self.mem_kind.get(),int(self.mem_importance.get()))
        else:self._mem_id=self.db.add_memory(txt,self.mem_tags.get(),self.mem_kind.get(),int(self.mem_importance.get()))
        self.refresh_memory()
    def delete_memory(self):
        if self._mem_id and messagebox.askyesno('Delete','Delete this memory?',parent=self):self.db.delete_memory(self._mem_id);self.new_memory();self.refresh_memory()

    # SKILLS
    def build_skills(self,page):
        self.header(page,'Skills','Aes capabilities are modular. Enable only the skills you want active.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));self.skill_tree=ttk.Treeview(body,columns=('cat','ver','state'),show='headings');
        for c,t,w in [('cat','Category',170),('ver','Version',100),('state','State',120)]:self.skill_tree.heading(c,text=t);self.skill_tree.column(c,width=w)
        self.skill_tree['columns']=('name','cat','ver','state');self.skill_tree.heading('name',text='Skill');self.skill_tree.column('name',width=280);self.skill_tree.pack(fill='both',expand=True);self.skill_tree.bind('<<TreeviewSelect>>',self.show_skill);bottom=Card(body,height=170);bottom.pack(fill='x',pady=(11,0));bottom.pack_propagate(False);self.skill_detail=tk.Text(bottom,bg=C.CARD,fg=C.TEXT,wrap='word',relief='flat',bd=0,padx=12,pady=10,font=('Segoe UI',9));self.skill_detail.pack(side='left',fill='both',expand=True);col=tk.Frame(bottom,bg=C.CARD,width=150);col.pack(side='right',fill='y',padx=10,pady=10);col.pack_propagate(False);self.button(col,'Enable / Disable',self.toggle_skill,accent=True).pack(fill='x');self.button(col,'Create custom',self.create_skill).pack(fill='x',pady=7);self._skill_rows=[]
    def refresh_skills(self):
        if not hasattr(self,'skill_tree'):return
        self.skill_tree.delete(*self.skill_tree.get_children());self._skill_rows=self.db.skills();
        for r in self._skill_rows:self.skill_tree.insert('','end',iid=str(r['id']),values=(r['name'],r['category'],r['version'],'Enabled' if r['enabled'] else 'Disabled'))
    def show_skill(self,_=None):
        sel=self.skill_tree.selection()
        if not sel:return
        r=next((x for x in self._skill_rows if str(x['id'])==sel[0]),None)
        if not r:return
        self.skill_detail.delete('1.0','end');self.skill_detail.insert('end',f"{r['name']}\n{r['description']}\n\n{r['instructions']}\n\nTools: {r['tools_json']}\nTriggers: {r['triggers_json']}")
    def toggle_skill(self):
        sel=self.skill_tree.selection()
        if not sel:return
        r=next(x for x in self._skill_rows if str(x['id'])==sel[0]);self.db.set_skill(r['id'],not r['enabled']);self.refresh_skills()
    def create_skill(self):
        n=simpledialog.askstring('Custom skill','Skill name:',parent=self)
        if not n:return
        ins=simpledialog.askstring('Custom skill','Core instruction:',parent=self) or 'Help with this skill carefully.';self.db.save_skill(n,'Custom','Owner-created skill',ins,[],[],version='1.0',enabled=1);self.refresh_skills()

    # TOOLS
    def build_tools(self,page):
        self.header(page,'Tools & Permissions','Every action has an owner policy: Allow, Ask, or Deny. State-changing tools default to Ask.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));self.tool_tree=ttk.Treeview(body,columns=('risk','policy','desc'),show='headings');
        for c,t,w in [('risk','Risk',100),('policy','Policy',100),('desc','Description',650)]:self.tool_tree.heading(c,text=t);self.tool_tree.column(c,width=w)
        self.tool_tree['columns']=('name','risk','policy','desc');self.tool_tree.heading('name',text='Tool');self.tool_tree.column('name',width=180);self.tool_tree.pack(fill='both',expand=True);bottom=Card(body,height=90);bottom.pack(fill='x',pady=(11,0));bottom.pack_propagate(False);inn=tk.Frame(bottom,bg=C.CARD);inn.pack(fill='both',expand=True,padx=14,pady=13);tk.Label(inn,text='Selected tool policy',bg=C.CARD,fg=C.MUTED).pack(side='left');self.policy_var=tk.StringVar(value='ask');ttk.Combobox(inn,textvariable=self.policy_var,state='readonly',values=['allow','ask','deny'],width=12).pack(side='left',padx=9);self.button(inn,'Apply',self.apply_policy,accent=True).pack(side='left');self.button(inn,'Open workspace',lambda:self.open_folder(self.tools.workspace)).pack(side='right')
    def refresh_tools(self):
        if not hasattr(self,'tool_tree'):return
        self.tool_tree.delete(*self.tool_tree.get_children());pol=self.db.policies()
        for n,t in self.tools.tools.items():self.tool_tree.insert('','end',iid=n,values=(n,t.risk,pol.get(n,'ask'),t.description))
    def apply_policy(self):
        sel=self.tool_tree.selection()
        if not sel:return
        self.db.set_policy(sel[0],self.policy_var.get());self.refresh_tools()

    # EVALS
    def build_evals(self,page):
        def right(m):return self.button(m,'Run eval suite',self.run_evals,accent=True)
        self.header(page,'Evals','Measure Aes versions before promoting changes. Improvements should beat regression gates.',right)
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));top=Card(body,height=120);top.pack(fill='x');top.pack_propagate(False);self.eval_summary=tk.Label(top,text='No eval run yet.',bg=C.CARD,fg=C.TEXT,font=('Segoe UI',16,'bold'));self.eval_summary.pack(anchor='w',padx=18,pady=(18,4));self.eval_sub=tk.Label(top,text='',bg=C.CARD,fg=C.MUTED);self.eval_sub.pack(anchor='w',padx=18);self.eval_tree=ttk.Treeview(body,columns=('model','score','passed','date'),show='headings');
        for c,t,w in [('model','Model',260),('score','Score',120),('passed','Passed',120),('date','Run',220)]:self.eval_tree.heading(c,text=t);self.eval_tree.column(c,width=w)
        self.eval_tree.pack(fill='both',expand=True,pady=(11,0))
    def refresh_evals(self):
        if not hasattr(self,'eval_tree'):return
        self.eval_tree.delete(*self.eval_tree.get_children());rows=self.db.eval_runs(30)
        for r in rows:self.eval_tree.insert('','end',values=(r['model_name'],f"{r['score']:.1f}%",f"{r['passed']}/{r['total']}",time.strftime('%Y-%m-%d %H:%M',time.localtime(r['created_at']))))
        if rows:self.eval_summary.configure(text=f"Latest: {rows[0]['score']:.1f}%");self.eval_sub.configure(text=f"{rows[0]['passed']} of {rows[0]['total']} checks passed on {rows[0]['model_name']}")
    def run_evals(self):
        model=self.chat_model.get() or self.db.setting('default_model','Aes 2.1 Local');self.side_status.configure(text='●  Running evals',fg=C.WARN)
        def work():
            try:res=self.evals.run(model);self.after(0,lambda:(self.refresh_evals(),messagebox.showinfo('Evals',f'{res[1]}/{res[2]} passed — {res[0]:.1f}%'),self.side_status.configure(text='●  Local core ready',fg=C.GOOD)))
            except Exception as e:self.after(0,lambda:(messagebox.showerror('Evals',str(e)),self.side_status.configure(text='●  Eval failed',fg=C.BAD)))
        threading.Thread(target=work,daemon=True).start()

    # TRAINING
    def build_training(self,page):
        self.header(page,'Training Lab','Turn approved conversations into datasets, create Aes candidates, then fine-tune locally on your GPU.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25));stats=tk.Frame(body,bg=C.BG);stats.pack(fill='x');self.train_count=self.stat_card(stats,'Training examples','0');self.feedback_count=self.stat_card(stats,'Feedback signals','0');self.candidate_count=self.stat_card(stats,'Candidates','0');actions=Card(body);actions.pack(fill='x',pady=12);inn=tk.Frame(actions,bg=C.CARD);inn.pack(fill='x',padx=15,pady=15);self.button(inn,'Collect 👍 feedback',self.collect_training,accent=True).pack(side='left');self.button(inn,'Export JSONL',self.export_training).pack(side='left',padx=7);self.button(inn,'Create LoRA candidate',self.create_candidate).pack(side='left');self.button(inn,'Open exports',lambda:self.open_folder(EXPORTS)).pack(side='right');self.cand_tree=ttk.Treeview(body,columns=('base','kind','status','score','date'),show='headings');
        for c,t,w in [('base','Base',210),('kind','Type',100),('status','Status',110),('score','Eval',100),('date','Created',180)]:self.cand_tree.heading(c,text=t);self.cand_tree.column(c,width=w)
        self.cand_tree['columns']=('name','base','kind','status','score','date');self.cand_tree.heading('name',text='Candidate');self.cand_tree.column('name',width=230);self.cand_tree.pack(fill='both',expand=True)
    def stat_card(self,parent,title,val):
        c=Card(parent,width=240,height=92);c.pack(side='left',fill='x',expand=True,padx=(0,10));c.pack_propagate(False);v=tk.Label(c,text=val,bg=C.CARD,fg=C.TEXT,font=('Segoe UI',20,'bold'));v.pack(anchor='w',padx=15,pady=(13,1));tk.Label(c,text=title,bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w',padx=15);return v
    def refresh_training(self):
        if not hasattr(self,'cand_tree'):return
        self.train_count.configure(text=str(len(self.db.training_examples())));self.feedback_count.configure(text=str(len(self.db.feedback(10000))));rows=self.db.candidates();self.candidate_count.configure(text=str(len(rows)));self.cand_tree.delete(*self.cand_tree.get_children())
        for r in rows:self.cand_tree.insert('','end',values=(r['name'],r['base_model'],r['kind'],r['status'],'' if r['eval_score'] is None else f"{r['eval_score']:.1f}%",time.strftime('%Y-%m-%d %H:%M',time.localtime(r['created_at']))))
    def collect_training(self):n=self.training.add_from_feedback();self.refresh_training();messagebox.showinfo('Training',f'Added {n} approved example(s).')
    def export_training(self):
        p,n=self.training.export_jsonl();messagebox.showinfo('Training',f'Exported {n} examples to:\n{p}')
    def create_candidate(self):
        name=simpledialog.askstring('Candidate','New Aes version name:',initialvalue='Aes 2.1 Candidate',parent=self)
        if not name:return
        base=self.chat_model.get() or 'Aes 2.1 Local';self.training.create_candidate(name,base,'Owner-created LoRA candidate');self.refresh_training()

    # UPDATES
    def build_updates(self,page):
        self.header(page,'Updates','Aes application and model-family roadmap. Your memories and projects remain separate from app binaries.')
        self.update_holder=tk.Frame(page,bg=C.BG);self.update_holder.pack(fill='both',expand=True,padx=28,pady=(0,25))
    def refresh_updates(self):
        if not hasattr(self,'update_holder'):return
        clear(self.update_holder)
        for r in self.db.versions():
            c=Card(self.update_holder);c.pack(fill='x',pady=6);inn=tk.Frame(c,bg=C.CARD);inn.pack(fill='x',padx=16,pady=13);tk.Label(inn,text=r['title'],bg=C.CARD,fg=C.TEXT,font=('Segoe UI',12,'bold')).pack(anchor='w');badge=tk.Label(inn,text=f"{r['channel'].upper()}  •  {r['status']}",bg=C.CARD2,fg=C.GOOD if r['status']=='installed' else C.MUTED,font=('Segoe UI',8),padx=8,pady=3);badge.place(relx=1.0,x=-2,y=0,anchor='ne');tk.Label(inn,text=r['notes'],bg=C.CARD,fg=C.MUTED,justify='left',wraplength=920,font=('Segoe UI',9)).pack(anchor='w',pady=(7,0))

    # SETTINGS
    def build_settings(self,page):
        self.header(page,'Settings','Owner configuration for local engines, training, external desktop tools and Aes Hub.')
        body=Card(page);body.pack(fill='both',expand=True,padx=28,pady=(0,25));inn=tk.Frame(body,bg=C.CARD);inn.pack(fill='both',expand=True,padx=20,pady=18);self.svars={k:tk.StringVar() for k in ['blender_path','unity_path','rojo_path','comfyui_url','hub_port','hub_token','auto_evolve','memory_enabled','agent_max_steps','autopilot_rounds']}
        for label,key in [('Blender executable','blender_path'),('Unity executable','unity_path'),('Rojo executable / command','rojo_path'),('Local ComfyUI URL','comfyui_url'),('Aes Hub port','hub_port'),('Aes Hub token (your owner API key)','hub_token'),('Max agent steps per request','agent_max_steps'),('Autopilot review rounds per goal','autopilot_rounds')]:self.label_field(inn,label.upper(),self.entry(inn,self.svars[key],show='•' if key=='hub_token' else None))
        checks=tk.Frame(inn,bg=C.CARD);checks.pack(fill='x',pady=10);self.mem_bool=tk.BooleanVar();self.evolve_bool=tk.BooleanVar();self.hub_agent_bool=tk.BooleanVar();ttk.Checkbutton(checks,text='Enable long-term memory',variable=self.mem_bool).pack(side='left');ttk.Checkbutton(checks,text='Auto-stage improvement candidates from feedback',variable=self.evolve_bool).pack(side='left',padx=25);ttk.Checkbutton(checks,text='Allow remote agent control via Hub (/v1/agent)',variable=self.hub_agent_bool).pack(side='left');act=tk.Frame(inn,bg=C.CARD);act.pack(fill='x',pady=12);self.button(act,'Save settings',self.save_settings,accent=True).pack(side='left');self.button(act,'Start local Aes Hub',self.start_hub).pack(side='left',padx=7);self.button(act,'Stop Hub',self.stop_hub).pack(side='left');tk.Label(inn,text=f'Data folder: {DATA}\nAes Hub binds to 127.0.0.1 by default. Use a proper authenticated HTTPS reverse proxy before exposing it publicly.',bg=C.CARD,fg=C.MUTED,justify='left').pack(anchor='w',pady=(15,0))
    def refresh_settings(self):
        if not hasattr(self,'svars'):return
        for k in ['blender_path','unity_path','rojo_path','comfyui_url','hub_port','hub_token','agent_max_steps','autopilot_rounds']:self.svars[k].set(self.db.setting(k,''))
        self.mem_bool.set(self.db.setting('memory_enabled','1')=='1');self.evolve_bool.set(self.db.setting('auto_evolve','1')=='1');self.hub_agent_bool.set(self.db.setting('hub_agent_enabled','0')=='1')
    def save_settings(self):
        for k in ['blender_path','unity_path','rojo_path','comfyui_url','hub_port','hub_token','agent_max_steps','autopilot_rounds']:self.db.set_setting(k,self.svars[k].get())
        self.db.set_setting('memory_enabled','1' if self.mem_bool.get() else '0');self.db.set_setting('auto_evolve','1' if self.evolve_bool.get() else '0');self.db.set_setting('hub_agent_enabled','1' if self.hub_agent_bool.get() else '0');self.side_status.configure(text='●  Settings saved',fg=C.GOOD)
    def start_hub(self):
        self.save_settings()
        try:self.hub.start('127.0.0.1',int(self.db.setting('hub_port','8765')));messagebox.showinfo('Aes Hub',f"Running locally on 127.0.0.1:{self.db.setting('hub_port','8765')}")
        except Exception as e:messagebox.showerror('Aes Hub',str(e))
    def stop_hub(self):self.hub.stop();messagebox.showinfo('Aes Hub','Stop requested.')

    # AUTOPILOT
    def build_autopilot(self,page):
        self.header(page,'Autopilot','Queue goals, set trust to Auto/Full, press Run — Aes works while you sleep and writes a morning report. Create a STOP file in the data folder to halt.')
        body=tk.Frame(page,bg=C.BG);body.pack(fill='both',expand=True,padx=28,pady=(0,25))
        left=Card(body);left.pack(side='left',fill='both',expand=True,padx=(0,13))
        self.goal_list=tk.Listbox(left,bg=C.CARD,fg=C.TEXT,selectbackground=C.CARD3,bd=0,highlightthickness=0);self.goal_list.pack(fill='both',expand=True,padx=9,pady=10);self.goal_list.bind('<<ListboxSelect>>',self.show_goal)
        right=Card(body,width=460);right.pack(side='left',fill='both');right.pack_propagate(False);inn=tk.Frame(right,bg=C.CARD);inn.pack(fill='both',expand=True,padx=16,pady=14)
        self.goal_title=tk.StringVar();self.goal_kind=tk.StringVar(value='task')
        self.label_field(inn,'GOAL',self.entry(inn,self.goal_title))
        tk.Label(inn,text='DEFINITION OF DONE / DETAIL',bg=C.CARD,fg=C.MUTED,font=('Segoe UI',8)).pack(anchor='w');self.goal_detail=self.text(inn,7);self.goal_detail.pack(fill='both',expand=True)
        row=tk.Frame(inn,bg=C.CARD);row.pack(fill='x',pady=8);ttk.Combobox(row,textvariable=self.goal_kind,state='readonly',values=['task','learn','video'],width=8).pack(side='left');self.button(row,'Queue goal',self.queue_goal,accent=True).pack(side='left',padx=7);self.button(row,'Delete',self.delete_goal,danger=True).pack(side='right')
        act=tk.Frame(inn,bg=C.CARD);act.pack(fill='x',pady=4);self.autopilot_btn=self.button(act,'☾  Run Autopilot now',self.run_autopilot,accent=True);self.autopilot_btn.pack(side='left');self.button(act,'Stop',self.stop_autopilot,danger=True).pack(side='left',padx=7);self.button(act,'Reports',lambda:self.open_folder(DATA/'reports')).pack(side='right');self.button(act,'Load training plan',self.load_curriculum).pack(side='right',padx=7);self.button(act,'Daily training',self.run_daily).pack(side='right')
        self.goal_view=self.text(inn,8);self.goal_view.pack(fill='both',expand=True,pady=(8,0));self._goals=[]
    def refresh_autopilot(self):
        if not hasattr(self,'goal_list'):return
        self._goals=self.db.goals();self.goal_list.delete(0,'end')
        for g in self._goals:self.goal_list.insert('end',f"  #{g['id']}  [{g['status']}]  ({g['kind']})  {g['title']}")
    def show_goal(self,_=None):
        s=self.goal_list.curselection()
        if not s:return
        g=self._goals[s[0]];self.goal_view.delete('1.0','end');self.goal_view.insert('1.0',f"{g['title']}\n\n{g['detail']}\n\n--- result ---\n{g['result']}")
    def queue_goal(self):
        t=self.goal_title.get().strip()
        if not t:return
        self.db.add_goal(t,self.goal_detail.get('1.0','end').strip(),self.goal_kind.get());self.goal_title.set('');self.goal_detail.delete('1.0','end');self.refresh_autopilot()
    def delete_goal(self):
        s=self.goal_list.curselection()
        if s:self.db.execute('DELETE FROM goals WHERE id=?',(self._goals[s[0]]['id'],));self.refresh_autopilot()
    def run_autopilot(self):
        from .autopilot import Autopilot,STOP_FILE
        if getattr(self,'_autopilot_running',False):return
        if self.db.setting('permission_mode','ask')=='ask' and not messagebox.askyesno('Autopilot','Trust mode is Ask: every risky action will wait for your click. Continue anyway? (Choose Auto or Full access in Chat for unattended runs.)',parent=self):return
        try:STOP_FILE.unlink()
        except Exception:pass
        self.db.set_setting('autopilot_stop','0');self._autopilot_running=True;self.autopilot_btn.configure(text='Autopilot running…',state='disabled');model=self.chat_model.get().strip()
        def work():
            err=None;report=None
            try:report=Autopilot(self.db,self.agent,log=lambda m:None).run_all(model)
            except Exception as e:err=e
            self.after(0,lambda:self._autopilot_done(report,err))
        threading.Thread(target=work,daemon=True).start()
    def _autopilot_done(self,report,err):
        self._autopilot_running=False;self.autopilot_btn.configure(text='☾  Run Autopilot now',state='normal');self.refresh_autopilot()
        if err:messagebox.showerror('Autopilot',str(err))
        elif report:self.side_status.configure(text='●  Autopilot report ready',fg=C.GOOD)
    def run_daily(self):
        from .daily import DailyTrainer
        if getattr(self,'_autopilot_running',False):return
        self._autopilot_running=True;self.autopilot_btn.configure(text='Daily training…',state='disabled');model=self.chat_model.get().strip();self.db.set_setting('autopilot_stop','0')
        def work():
            err=None;report=None
            try:report=DailyTrainer(self.db,self.agent,log=lambda m:None).run(model)
            except Exception as e:err=e
            self.after(0,lambda:self._autopilot_done(report,err))
        threading.Thread(target=work,daemon=True).start()
    def load_curriculum(self):
        from .curriculum import queue,tracks
        t=simpledialog.askstring('Training plan','Tracks to queue (all, or comma list):\n'+', '.join(tracks()),initialvalue='all',parent=self)
        if t:n=queue(self.db,t.strip());self.refresh_autopilot();messagebox.showinfo('Training plan',f'Queued {n} goal(s).',parent=self)
    def stop_autopilot(self):self.db.set_setting('autopilot_stop','1');self.side_status.configure(text='●  Autopilot stopping after current step',fg=C.WARN)

    def ask_tool_permission(self,req):
        box={'ok':False};ev=threading.Event()
        def ask():
            box['ok']=messagebox.askyesno('Aes tool permission',f"Aes wants to run:\n\n{req.tool_name}\nRisk: {req.risk}\n\n{req.summary}\n\nAllow this action?",parent=self);ev.set()
        self.after(0,ask);ev.wait();return box['ok']
    def open_folder(self,path):
        p=str(Path(path).resolve())
        try:
            if os.name=='nt':os.startfile(p)
            else:webbrowser.open('file://'+p)
        except Exception as e:messagebox.showerror('Open folder',str(e))
    def refresh_all(self):
        for k in ['chat','projects','models','knowledge','memory','skills','tools','evals','autopilot','training','updates','settings']:
            try:getattr(self,f'refresh_{k}')()
            except Exception:pass
        self.refresh_project_choices()
    def on_close(self):
        try:self.hub.stop();self.runtimes.unload();self.db.close()
        finally:self.destroy()
