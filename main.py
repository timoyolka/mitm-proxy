import asyncio
import threading
import queue
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from proxy import AsyncProxy

HOST = "0.0.0.0"
PORT = 8080

def main():
    proxy = AsyncProxy(host=HOST, port=PORT)
    proxy.start_gui()

if __name__ == "__main__":
    main()