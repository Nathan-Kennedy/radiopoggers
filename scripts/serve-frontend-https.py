#!/usr/bin/env python3
"""Serve o frontend RadioPoggers com HTTPS + proxy (API, AzuraCast, stream, capas)."""

from __future__ import annotations

import http.client
import os
import ssl
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SSL_DIR = PROJECT_ROOT / "data" / "dev-ssl"
CERT_FILE = SSL_DIR / "radiopoggers.crt"
KEY_FILE = SSL_DIR / "radiopoggers.key"
PORT = int(os.environ.get("RADIOPOGGERS_HTTPS_PORT", "5443"))
API_PREFIX = "/radiopoggers-api"
AZURACAST_PREFIX = "/azuracast"
API_UPSTREAM = os.environ.get("RADIOPOGGERS_API_UPSTREAM", "http://127.0.0.1:8765").rstrip("/")
AZURACAST_UPSTREAM = os.environ.get("RADIOPOGGERS_AZURACAST_UPSTREAM", "http://127.0.0.1").rstrip("/")
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def upstream_parts(base_url: str) -> tuple[str, int, bool]:
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.hostname or "127.0.0.1"
    secure = parsed.scheme == "https"
    if parsed.port:
        port = parsed.port
    else:
        port = 443 if secure else 80
    return host, port, secure


class RadioPoggersHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        print(f"[HTTPS frontend] {self.address_string()} - {format % args}")

    def _read_request_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return None
        return self.rfile.read(length)

    def _forward_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            if key.lower() in HOP_BY_HOP_HEADERS or key.lower() == "host":
                continue
            headers[key] = value
        return headers

    def _proxy_to(self, upstream_base: str, target_path: str) -> None:
        host, port, secure = upstream_parts(upstream_base)
        if not target_path.startswith("/"):
            target_path = f"/{target_path}"

        body = self._read_request_body()
        headers = self._forward_headers()
        conn: http.client.HTTPConnection | http.client.HTTPSConnection
        if secure:
            conn = http.client.HTTPSConnection(host, port, timeout=120)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=120)

        try:
            conn.request(self.command, target_path, body=body, headers=headers)
            upstream = conn.getresponse()
            self.send_response(upstream.status, upstream.reason)

            content_type = ""
            for key, value in upstream.getheaders():
                lower = key.lower()
                if lower in HOP_BY_HOP_HEADERS:
                    continue
                if lower == "content-type":
                    content_type = value
                self.send_header(key, value)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            stream = "text/event-stream" in content_type.lower()
            while True:
                chunk = upstream.read(65536 if stream else -1)
                if not chunk:
                    break
                self.wfile.write(chunk)
                if stream:
                    self.wfile.flush()
        finally:
            conn.close()

    def _dispatch_proxy(self) -> bool:
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        query = parsed.query

        if path == API_PREFIX or path.startswith(f"{API_PREFIX}/"):
            target = path[len(API_PREFIX):] or "/"
            if query:
                target = f"{target}?{query}"
            self._proxy_to(API_UPSTREAM, target)
            return True

        if path == AZURACAST_PREFIX or path.startswith(f"{AZURACAST_PREFIX}/"):
            target = path[len(AZURACAST_PREFIX):] or "/"
            if query:
                target = f"{target}?{query}"
            self._proxy_to(AZURACAST_UPSTREAM, target)
            return True

        return False

    def do_OPTIONS(self) -> None:
        if self._dispatch_proxy():
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self) -> None:
        if self._dispatch_proxy():
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self._dispatch_proxy():
            return
        super().do_HEAD()

    def do_POST(self) -> None:
        if self._dispatch_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self) -> None:
        if self._dispatch_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_PATCH(self) -> None:
        if self._dispatch_proxy():
            return
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self) -> None:
        if self._dispatch_proxy():
            return
        self.send_error(405, "Method Not Allowed")


def main() -> int:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print("Certificado dev ausente. Rode: .\\scripts\\ensure-dev-ssl.ps1")
        return 1

    server = ThreadingHTTPServer(("0.0.0.0", PORT), RadioPoggersHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if hasattr(ssl, "TLSVersion"):
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
    try:
        context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!DSS")
    except ssl.SSLError:
        pass
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"Frontend HTTPS em https://0.0.0.0:{PORT}/frontend/")
    print(f"  Proxy API:      {API_UPSTREAM}  ->  /radiopoggers-api/")
    print(f"  Proxy AzuraCast:{AZURACAST_UPSTREAM}  ->  /azuracast/")
    print("No celular/Radmin: aceite o certificado autoassinado na 1a visita.")
    print("Se o celular ficar carregando infinito: servidor parado ou firewall.")
    print("  Teste: .\\scripts\\test-https-frontend.ps1")
    print("  Firewall (Admin): .\\scripts\\open-lan-firewall.ps1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando HTTPS frontend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
