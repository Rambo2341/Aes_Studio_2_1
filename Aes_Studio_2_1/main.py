import sys

if __name__=='__main__':
    if sys.argv[1:]==['--tk-ui']:
        from aes.paths import DB_PATH
        from aes.ui import AesStudio
        AesStudio(DB_PATH).mainloop(); sys.exit(0)
    if len(sys.argv)>1:
        # Headless: python main.py --chat | --autopilot | --goal "..." | --learn "..." | --api | --status
        from aes.cli import main
        sys.exit(main(sys.argv[1:]))
    from aes.paths import DB_PATH
    # New Qt interface when PySide6 is installed; the classic Tk interface stays as a fallback (python main.py --tk-ui).
    try:
        from aes.qt_ui import run
    except Exception:
        run=None
    if run:
        sys.exit(run(DB_PATH))
    from aes.ui import AesStudio
    app=AesStudio(DB_PATH)
    app.mainloop()
