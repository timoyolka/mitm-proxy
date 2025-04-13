import asyncio
<<<<<<< HEAD
import threading
import queue
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
=======
import sys
from pathlib import Path
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9
from proxy import AsyncProxy

HOST = "0.0.0.0"
PORT = 8080
<<<<<<< HEAD

def main():
    proxy = AsyncProxy(host=HOST, port=PORT)
    proxy.start_gui()
=======
CERT_PATH = Path("certs/mitm_cert.crt").resolve()
KEY_PATH = Path("certs/mitm_cert.key").resolve()

def main():
    proxy = AsyncProxy(host=HOST, port=PORT)
    asyncio.run(proxy.start())
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9

if __name__ == "__main__":
    main()