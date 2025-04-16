import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

class ProxyGUI(tk.Tk):
    def __init__(self, start_proxy_fn):
        super().__init__()
        self.title("Proxy Inspector")
        self.geometry("1000x600")
        
        self.start_proxy_fn = start_proxy_fn 

        self.request_data = {}  # index -> full request/response text
        self.create_toolbar()
        self.create_main_panes()

    def create_toolbar(self):
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        start_btn = ttk.Button(toolbar, text="Start Proxy", command=self.start_proxy)
        stop_btn = ttk.Button(toolbar, text="Stop Proxy", command=self.stop_proxy)
        config_btn = ttk.Button(toolbar, text="Settings", command=self.open_settings)

        start_btn.pack(side=tk.LEFT, padx=2)
        stop_btn.pack(side=tk.LEFT, padx=2)
        config_btn.pack(side=tk.LEFT, padx=2)

    def create_main_panes(self):
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Left panel - List of requests/responses
        left_frame = ttk.Frame(main_pane, width=300)
        self.request_list = tk.Listbox(left_frame)
        self.request_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.request_list.bind("<<ListboxSelect>>", self.display_request_details)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.request_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.request_list.config(yscrollcommand=scrollbar.set)

        # Right panel - Text window
        right_frame = ttk.Frame(main_pane)
        self.detail_view = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD)
        self.detail_view.pack(fill=tk.BOTH, expand=True)

        main_pane.add(left_frame, weight=1)
        main_pane.add(right_frame, weight=3)

    # ---------------------- Toolbar Actions ----------------------
    def start_proxy(self):
        print("Starting proxy...")
        threading.Thread(target=self.start_proxy_fn, daemon=True).start()
    def stop_proxy(self):
        print("Stopping proxy...")

    def open_settings(self):
        print("Opening settings...")

    # ---------------------- Request Management ----------------------
    def add_message(self, summary: str, full_text: str = ""):
        index = self.request_list.size()
        self.request_list.insert(tk.END, summary)
        self.request_data[index] = full_text

    def remove_request(self, index: int):
        if 0 <= index < self.request_list.size():
            self.request_list.delete(index)
            self.request_data.pop(index, None)
            # Re-index remaining items
            self.request_data = {
                i: self.request_data.get(j, "")
                for i, j in enumerate(sorted(self.request_data))
                if i < self.request_list.size()
            }

    def clear_requests(self):
        self.request_list.delete(0, tk.END)
        self.request_data.clear()
        self.detail_view.delete("1.0", tk.END)

    def get_selected_index(self):
        selection = self.request_list.curselection()
        return selection[0] if selection else None

    def display_request_details(self, event=None):
        index = self.get_selected_index()
        if index is not None:
            full_text = self.request_data.get(index, "[No details available]")
            self.detail_view.delete("1.0", tk.END)
            self.detail_view.insert(tk.END, full_text)