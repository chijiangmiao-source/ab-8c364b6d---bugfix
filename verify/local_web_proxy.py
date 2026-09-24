"""Local stand-in for the production nginx: serves the built SPA and proxies
/api and /health to FastAPI.  Used only for host-side verification."""

import http.server
import http.client
import os
import urllib.parse

DIST = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
API_HOST, API_PORT = "127.0.0.1", 8000


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(DIST), **kwargs)

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path == "/health" or self.path.startswith("/api/"):
            self._proxy()
            return
        if "." not in os.path.basename(urllib.parse.urlparse(self.path).path):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(404)

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=10)
        conn.request(self.command, self.path, body=body, headers=self._proxy_headers())
        resp = conn.getresponse()
        data = resp.read()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in ("transfer-encoding", "connection"):
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _proxy_headers(self):
        return {
            k: v for k, v in self.headers.items() if k.lower() != "host"
        } | {"Host": f"{API_HOST}:{API_PORT}"}

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    http.server.HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
