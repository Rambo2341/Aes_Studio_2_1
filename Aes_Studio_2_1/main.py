from aes.paths import DB_PATH
from aes.ui import AesStudio

if __name__=='__main__':
    app=AesStudio(DB_PATH)
    app.mainloop()
