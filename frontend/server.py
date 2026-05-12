#!/usr/bin/env python3
"""
前端服务器
端口: 1314
"""

import os
import http.server
import socketserver
from pathlib import Path

PORT = 1314
DIRECTORY = Path(__file__).parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def log_message(self, format, *args):
        print(f"[Frontend] {args[0]}")

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🎨 Frontend server started on http://127.0.0.1:{PORT}")
        print(f"📊 Dashboard: http://127.0.0.1:{PORT}/index.html")
        httpd.serve_forever()
