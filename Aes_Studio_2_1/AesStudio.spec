# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
hidden=[]
for pkg in ['fastapi','uvicorn','pydantic','docx','pypdf','anthropic','pyautogui','pyperclip']:
    try:hidden += collect_submodules(pkg)
    except Exception:pass

a=Analysis(['main.py'],pathex=[],binaries=[],datas=[('assets','assets'),('identity','identity'),('skills','skills')],hiddenimports=hidden,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False,optimize=1)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='AesStudio',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,console=False,icon='assets/aes.ico',version='version_info.txt')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=True,upx_exclude=[],name='AesStudio')
