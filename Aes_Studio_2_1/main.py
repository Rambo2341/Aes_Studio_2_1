import sys

if __name__=='__main__':
    if len(sys.argv)>1:
        # Headless: python main.py --chat | --autopilot | --goal "..." | --learn "..." | --api | --status
        from aes.cli import main
        sys.exit(main(sys.argv[1:]))
    from aes.paths import DB_PATH
    from aes.ui import AesStudio
    app=AesStudio(DB_PATH)
    app.mainloop()
