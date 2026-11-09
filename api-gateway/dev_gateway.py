"""Lightweight development API Gateway for local Windows environments without Docker/Nginx.

Routes requests on port 8000:
  /auth/*          -> http://127.0.0.1:8001/*
  /academic/*      -> http://127.0.0.1:8002/*
  /registrations/* -> http://127.0.0.1:8003/*
  /topics/*        -> http://127.0.0.1:8004/*
  /docs/, /swagger/-> Serves Swagger UI (swagger/index.html & openapi.yaml)
  /openapi.yaml    -> Serves swagger/openapi.yaml
  /health/         -> 200 {"status":"ok","service":"api-gateway-dev"}

Returns HTTP 503 {"detail":"Service unavailable."} when an upstream service is down.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dev_gateway")

ROOT = Path(__file__).resolve().parents[1]
SWAGGER_DIR = ROOT / "swagger"

SERVICE_ROUTES = {
    "/auth/": "http://127.0.0.1:8001",
    "/academic/": "http://127.0.0.1:8002",
    "/registrations/": "http://127.0.0.1:8003",
    "/topics/": "http://127.0.0.1:8004",
}

HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def add_cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Request-ID, Accept, Origin, *")


class DevGatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self):
        self.send_response(200)
        add_cors_headers(self)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.handle_proxy(send_body=False)

    def do_GET(self):
        self.handle_proxy(send_body=True)

    def do_POST(self):
        self.handle_proxy(send_body=True)

    def do_PUT(self):
        self.handle_proxy(send_body=True)

    def do_PATCH(self):
        self.handle_proxy(send_body=True)

    def do_DELETE(self):
        self.handle_proxy(send_body=True)

    def handle_proxy(self, send_body=True):
        raw_path = self.path
        parsed_path = raw_path.split("?")[0]
        query = ("?" + raw_path.split("?", 1)[1]) if "?" in raw_path else ""

        # 1. Health check
        if parsed_path in ("/health", "/health/"):
            data = json.dumps({"status": "ok", "service": "api-gateway-dev"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            add_cors_headers(self)
            self.end_headers()
            if send_body:
                self.wfile.write(data)
            return

        # 2. Block internal auth policy (same as Nginx config)
        if parsed_path == "/auth/internal" or parsed_path.startswith("/auth/internal/"):
            data = json.dumps({"detail": "Not found."}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            add_cors_headers(self)
            self.end_headers()
            if send_body:
                self.wfile.write(data)
            return

        # 3. Serve Swagger UI documentation
        if parsed_path in ("/docs", "/docs/", "/swagger", "/swagger/", "/swagger/index.html", "/docs/index.html"):
            index_path = SWAGGER_DIR / "index.html"
            if index_path.is_file():
                content = index_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                add_cors_headers(self)
                self.end_headers()
                if send_body:
                    self.wfile.write(content)
                return

        if parsed_path in ("/openapi.yaml", "/docs/openapi.yaml", "/swagger/openapi.yaml"):
            yaml_path = SWAGGER_DIR / "openapi.yaml"
            if yaml_path.is_file():
                content = yaml_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/yaml; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                add_cors_headers(self)
                self.end_headers()
                if send_body:
                    self.wfile.write(content)
                return

        # 4. Route to backend services
        target_base = None
        forwarded_path = None
        for prefix, base_url in SERVICE_ROUTES.items():
            if parsed_path == prefix[:-1]:  # E.g. /auth without trailing slash
                target_base = base_url
                forwarded_path = "/" + query
                break
            if parsed_path.startswith(prefix):
                target_base = base_url
                # Strip prefix, keeping remaining path (prefix forwards to '/')
                forwarded_path = parsed_path[len(prefix) - 1:] + query
                break

        if not target_base:
            data = json.dumps({"detail": "Not found."}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            add_cors_headers(self)
            self.end_headers()
            if send_body:
                self.wfile.write(data)
            return

        upstream_url = target_base + forwarded_path

        # Read request body if present
        body = None
        content_length = self.headers.get("Content-Length")
        if content_length:
            try:
                body = self.rfile.read(int(content_length))
            except Exception:
                body = None

        # Build upstream request
        upstream_req = urllib.request.Request(upstream_url, data=body, method=self.command)
        for key, value in self.headers.items():
            if key.lower() not in HOP_BY_HOP_HEADERS:
                upstream_req.add_header(key, value)

        # Set or preserve X-Request-ID
        if "X-Request-ID" not in upstream_req.headers:
            upstream_req.add_header("X-Request-ID", f"gw-{os.urandom(4).hex()}")

        try:
            with urllib.request.urlopen(upstream_req, timeout=10) as response:
                resp_code = response.status
                resp_body = response.read()
                self.send_response(resp_code)
                for header_key, header_val in response.getheaders():
                    if header_key.lower() not in HOP_BY_HOP_HEADERS:
                        self.send_header(header_key, header_val)
                add_cors_headers(self)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                if send_body:
                    self.wfile.write(resp_body)
        except urllib.error.HTTPError as exc:
            err_body = exc.read()
            self.send_response(exc.code)
            for header_key, header_val in exc.headers.items():
                if header_key.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(header_key, header_val)
            add_cors_headers(self)
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            if send_body:
                self.wfile.write(err_body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Backend service is down or unreachable -> 503 Service Unavailable
            logger.warning("Upstream failure for %s: %s", upstream_url, exc)
            err_data = json.dumps({"detail": "Service unavailable."}).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_data)))
            add_cors_headers(self)
            self.end_headers()
            if send_body:
                self.wfile.write(err_data)

    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)


def run_dev_gateway(host="0.0.0.0", port=8000):
    server = ThreadingHTTPServer((host, port), DevGatewayHandler)
    logger.info("Dev API Gateway running on http://%s:%d", host, port)
    logger.info("Swagger UI available at: http://localhost:%d/docs/", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dev API Gateway stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_dev_gateway(port=port)
