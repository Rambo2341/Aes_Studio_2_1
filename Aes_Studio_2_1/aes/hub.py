from __future__ import annotations
import hmac,threading
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel
import uvicorn

class ChatBody(BaseModel):
    message: str
    model: str | None = None

class AgentBody(BaseModel):
    message: str
    model: str | None = None
    conversation_id: str | None = None
    project_id: str | None = None

class GoalBody(BaseModel):
    title: str
    detail: str = ''
    kind: str = 'task'

class AesHub:
    """Aes owner API. Bind to 127.0.0.1; put an authenticated HTTPS tunnel/proxy in front before exposing it.

    /v1/chat   plain chat, no tools.
    /v1/agent  full Aes agent with the owner's tools (disabled unless Settings -> hub_agent_enabled = 1).
               There is nobody to click "Approve" on this path, so only tools allowed by the current
               permission mode (Auto policies / Full access) will run.
    /v1/goals  queue Autopilot goals remotely (e.g. from your phone before sleeping).
    """
    def __init__(self,db,runtimes,agent=None):
        self.db=db; self.runtimes=runtimes; self.agent=agent; self.thread=None; self.server=None
        self.app=FastAPI(title='Aes Hub',version='2.2')
        self._routes()
    def _auth(self,authorization):
        expected=self.db.setting('hub_token','')
        got=(authorization or '').removeprefix('Bearer ').strip()
        if not expected or expected=='change-me' or not got or not hmac.compare_digest(got,expected):
            raise HTTPException(401,'Invalid Aes Hub token')
    def _model_name(self,name):
        name=name or self.db.setting('default_model','Aes 2.1 Local')
        if not self.db.model(name): raise HTTPException(404,'Model not found')
        return name
    def _routes(self):
        @self.app.get('/health')
        def health(): return {'ok':True,'service':'Aes Hub','version':'2.2'}
        @self.app.post('/v1/chat')
        def chat(body:ChatBody,authorization:str|None=Header(default=None)):
            self._auth(authorization); name=self._model_name(body.model); model=self.db.model(name)
            ans=self.runtimes.complete(model,[{'role':'system','content':model['system_prompt']+'\nYou are responding through Aes Hub. You have no owner tools in this request.'},{'role':'user','content':body.message}])
            return {'model':name,'reply':ans}
        @self.app.post('/v1/agent')
        def agent(body:AgentBody,authorization:str|None=Header(default=None)):
            self._auth(authorization)
            if self.db.setting('hub_agent_enabled','0')!='1' or not self.agent:
                raise HTTPException(403,'Remote agent control is disabled. Enable hub_agent_enabled in Settings.')
            name=self._model_name(body.model)
            cid=body.conversation_id or self.db.new_conversation('Hub: '+body.message[:50],body.project_id,name)
            ans,mid,traces=self.agent.run(cid,name,body.message,'agent',body.project_id)
            self.db.log('hub_agent',body.message[:200],True)
            return {'model':name,'conversation_id':cid,'reply':ans,'tools':[{'tool':t['tool'],'result':str(t['result'])[:2000]} for t in traces]}
        @self.app.post('/v1/goals')
        def add_goal(body:GoalBody,authorization:str|None=Header(default=None)):
            self._auth(authorization)
            gid=self.db.add_goal(body.title,body.detail,body.kind if body.kind in ('task','learn','video') else 'task')
            return {'id':gid,'status':'queued'}
        @self.app.get('/v1/goals')
        def list_goals(authorization:str|None=Header(default=None)):
            self._auth(authorization)
            return [{k:g[k] for k in ('id','kind','title','status','result')} for g in self.db.goals()[:100]]
    def start(self,host='127.0.0.1',port=8765):
        if self.thread and self.thread.is_alive(): return
        config=uvicorn.Config(self.app,host=host,port=int(port),log_level='warning')
        self.server=uvicorn.Server(config)
        self.thread=threading.Thread(target=self.server.run,daemon=True); self.thread.start()
    def stop(self):
        if self.server: self.server.should_exit=True
