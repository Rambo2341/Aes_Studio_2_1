from __future__ import annotations
from dataclasses import dataclass
import threading

RISK_SAFE='safe'
RISK_WRITE='write'
RISK_EXEC='exec'
RISK_NETWORK='network'
RISK_COMPUTER='computer'
RISK_SYSTEM='system'

@dataclass
class PermissionRequest:
    tool_name: str
    risk: str
    summary: str
    arguments: dict

class PermissionDenied(RuntimeError): pass

class PermissionManager:
    def __init__(self, db, ask_callback=None):
        self.db=db
        self.ask_callback=ask_callback
        self._lock=threading.RLock()

    def mode(self, tool_name, risk='safe'):
        policies=self.db.policies()
        if tool_name in policies: return policies[tool_name]
        return 'allow' if risk=='safe' else ('deny' if risk=='system' else 'ask')

    def authorize(self, tool_name, risk, summary, arguments):
        # Session-wide trust mode mirrors the Aes Studio composer control.
        # Hard destructive-command blocks still live in ToolRegistry and are never bypassed.
        trust=(self.db.setting('permission_mode','ask') or 'ask').lower()
        if trust=='full':
            self.db.log('tool_permission',f'{tool_name}: full-access ({summary})',True); return True
        if trust=='ask' and risk!='safe':
            mode='ask'
        else:
            mode=self.mode(tool_name,risk)
        if mode=='allow':
            self.db.log('tool_permission',f'{tool_name}: allow ({summary})',True); return True
        if mode=='deny':
            self.db.log('tool_permission',f'{tool_name}: denied ({summary})',False)
            raise PermissionDenied(f"Tool '{tool_name}' is blocked by your Aes policy.")
        if not self.ask_callback:
            self.db.log('tool_permission',f'{tool_name}: ask unavailable',False)
            raise PermissionDenied(f"Tool '{tool_name}' requires owner approval, but no approval UI is available.")
        req=PermissionRequest(tool_name,risk,summary,arguments)
        ok=bool(self.ask_callback(req))
        self.db.log('tool_permission',f'{tool_name}: owner={ok} ({summary})',ok)
        if not ok: raise PermissionDenied(f"Owner denied tool '{tool_name}'.")
        return True
