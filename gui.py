import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime

class ProxyGUI(tk.Tk):
    def __init__(self, start_proxy_fn, stop_proxy_fn):
        super().__init__()
        self.title("Proxy Inspector")
        self.geometry("1200x700")

        self.start_proxy_fn = start_proxy_fn
        self.packet_data = {}  # packet_no -> full packet data
        self.packet_counter = 0

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

        filter_label = ttk.Label(toolbar, text="Filter by:")
        filter_label.pack(side=tk.LEFT, padx=(20, 2))

        self.filter_type = tk.StringVar(value="URL")
        filter_options = ttk.Combobox(toolbar, textvariable=self.filter_type,
                                      values=["URL", "Method", "Content-Type"],
                                      state="readonly", width=15)
        filter_options.pack(side=tk.LEFT, padx=2)

        self.filter_entry = ttk.Entry(toolbar, width=30)
        self.filter_entry.pack(side=tk.LEFT, padx=2)

        filter_btn = ttk.Button(toolbar, text="Apply Filter", command=self.apply_filter)
        filter_btn.pack(side=tk.LEFT, padx=2)

    def create_main_panes(self):
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Left: Treeview (Wireshark-style table)
        left_frame = ttk.Frame(main_pane, width=500)
        self.tree = ttk.Treeview(left_frame, columns=(
            "No", "Time", "Source", "Destination", "Protocol", "Length", "Info"),
            show="headings", height=25)

        # Configure columns
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor=tk.W, stretch=True)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.display_request_details)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Right: Scrolled text area for full packet
        right_frame = ttk.Frame(main_pane)
        self.detail_view = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD)
        self.detail_view.pack(fill=tk.BOTH, expand=True)

        main_pane.add(left_frame, weight=2)
        main_pane.add(right_frame, weight=3)

    def start_proxy(self):
        print("Starting proxy...")
        threading.Thread(target=self.start_proxy_fn, daemon=True).start()

    def stop_proxy(self):
        print("Stopping proxy...")
        if hasattr(self, "proxy") and self.proxy:
            # Run the stop_proxy asynchronously in the event loop
            asyncio.run_coroutine_threadsafe(self.proxy.stop_proxy(), self.proxy.loop)
            
    def open_settings(self):
        print("Opening settings...")

    def add_message(self, packet_no, timestamp, source, destination, protocol, length, info,
                full_text, method=""):
        # Add to Treeview
        self.tree.insert("", tk.END, iid=packet_no, values=(
            packet_no, timestamp, source, destination, protocol, length, info))

        # Save full data
        self.packet_data[packet_no] = {
            "summary": info,
            "full_text": full_text,
            "method": method,
        }

    def display_request_details(self, event=None):
        selected = self.tree.selection()
        if selected:
            packet_no = int(selected[0])
            packet_info = self.packet_data.get(packet_no, {})
            full_text = packet_info.get("full_text", "[No details available]")
            self.detail_view.delete("1.0", tk.END)
            self.detail_view.insert(tk.END, full_text)

    def apply_filter(self):
        filter_key = self.filter_type.get().lower()
        filter_value = self.filter_entry.get().strip().lower()

        # Clear current view
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Re-populate filtered data
        for packet_no, data in self.packet_data.items():
            method = data.get("method", "").lower()
            url = data.get("url", "").lower()
            content_type = data.get("content_type", "").lower()
            summary = data.get("summary", "")
            full_text = data.get("full_text", "")

            if (filter_key == "method" and filter_value in method) or \
               (filter_key == "url" and filter_value in url) or \
               (filter_key == "content-type" and filter_value in content_type):
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                source = "client"
                destination = "server"
                protocol = "HTTPS"
                length = len(full_text)

                self.tree.insert("", tk.END, iid=packet_no, values=(
                    packet_no, timestamp, source, destination, protocol, length, summary))
