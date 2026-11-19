"""The small web server behind the board views: one HTML page, server-sent events for
state updates, and POST endpoints for input. Standard library only; listens on
127.0.0.1, so nothing is reachable from other machines."""
import json
import queue
import signal
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"


class Hub:
    """Fans events out to every open page, and keeps what a newly opened page needs."""

    def __init__(self, keep=("status", "state"), console=300):
        self.lock = threading.Lock()
        self.clients = []
        self.latest = {}                 # last event of each kept type
        self.keep = keep
        self.console = []                # last UART lines
        self.console_max = console

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.clients.append(q)
            backlog = [self.latest[t] for t in self.keep if t in self.latest]
            backlog[1:1] = [{"t": "uart", "line": l} for l in self.console]
        for ev in backlog:
            q.put(ev)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def publish(self, ev):
        with self.lock:
            if ev["t"] in self.keep:
                self.latest[ev["t"]] = ev
            elif ev["t"] == "uart":
                self.console = (self.console + [ev["line"]])[-self.console_max:]
            elif ev["t"] == "reset":
                self.latest.pop("state", None)
                self.console = []
            clients = list(self.clients)
        for q in clients:
            q.put(ev)


def serve(page, hub, hello, routes, port=8737, open_browser=True, on_stop=lambda: None):
    """Serve `page` (a file in web/) until Quit, Ctrl-C, SIGTERM or SIGHUP.
    routes: {"/input": fn(body), ...} for POST requests."""
    page_path = WEB / page

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body=b"", ctype="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, page_path.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/events":
                self._events()
            else:
                self._send(404, b"not found")

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode("ascii", "ignore")
            if self.path == "/quit":
                self._send(204)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            elif self.path in routes:
                routes[self.path](body)
                self._send(204)
            else:
                self._send(404, b"not found")

        def _events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            q = hub.subscribe()
            try:
                self._write(hello)
                while True:
                    try:
                        self._write(q.get(timeout=15))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                hub.unsubscribe(q)

        def _write(self, ev):
            self.wfile.write(b"data: " + json.dumps(ev).encode() + b"\n\n")
            self.wfile.flush()

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:                       # port in use: take any free one
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_address[1]}/"

    # SIGTERM / SIGHUP (kill, closed terminal) would end Python without the finally
    # below and leave the simulator running: treat them like Ctrl-C.
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, interrupt)

    print(f"Board view: {url}", flush=True)
    print("Close with the Quit button on the page or Ctrl-C here.", flush=True)
    if open_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        on_stop()
        server.server_close()
        print("stopped")
