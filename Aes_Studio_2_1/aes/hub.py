from __future__ import annotations
import secrets,threading
from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel
import uvicorn

class ChatBody(BaseModel):
    message: str
    model: str | None = None

class AesHub:
    def __init__(self,db,runtimes):
        self.db=db; self.runtimes=runtimes; self.thread=None; self.server=None
        self.app=FastAPI(title='Aes Hub',version='2.0')
        self._routes()
    def _auth(self,authorization):
        expected=self.db.setting('hub_token','change-me')
        if not authorization or authorization.removeprefix('Bearer ').strip()!=expected: raise HTTPException(401,'Invalid Aes Hub token')
    def _routes(self):
        @self.app.get('/health')
        def health(): return {'ok':True,'service':'Aes Hub','version':'2.0'}
        @self.app.post('/v1/chat')
        def chat(body:ChatBody,authorization:str|None=Header(default=None)):
            self._auth(authorization)
            name=body.model or self.db.setting('default_model','Aes 2.1 Local'); model=self.db.model(name)
            if not model: raise HTTPException(404,'Model not found')
            # Public Hub deliberately has no owner desktop/filesystem tools.
            ans=self.runtimes.complete(model,[{'role':'system','content':model['system_prompt']+'\nYou are responding through Aes Hub. You have no owner tools in this request.'},{'role':'user','content':body.message}])
            return {'model':name,'reply':ans}
    def start(self,host='127.0.0.1',port=8765):
        if self.thread and self.thread.is_alive(): return
        config=uvicorn.Config(self.app,host=host,port=int(port),log_level='warning')
        self.server=uvicorn.Server(config)
        self.thread=threading.Thread(target=self.server.run,daemon=True); self.thread.start()
    def stop(self):
        if self.server: self.server.should_exit=True
