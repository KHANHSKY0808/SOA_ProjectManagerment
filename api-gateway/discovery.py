"""Consul discovery and Nginx supervision. No domain logic or shared ORM."""
import ipaddress
import json
import logging
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

ROUTES = {"auth": "auth-service", "academic": "academic-service",
          "registrations": "regist-service", "topics": "topic-service"}
LOG = logging.getLogger("gateway.discovery")

# DNS APIs have no per-call timeout. A short-lived child lets the parent kill
# and reap a stalled lookup instead of accumulating abandoned resolver threads.
IPV4_LOOKUP = """
import json, socket, sys
hosts = json.load(sys.stdin)
result = {host: sorted({entry[4][0] for entry in socket.getaddrinfo(
    host, None, socket.AF_INET, socket.SOCK_STREAM)}) for host in hosts}
json.dump(result, sys.stdout)
"""


def resolve_ipv4(hosts, timeout):
    if not hosts:
        return {}
    try:
        result = subprocess.run([sys.executable, "-c", IPV4_LOOKUP],
                                input=json.dumps(sorted(hosts)), capture_output=True,
                                text=True, timeout=timeout, check=True)
        if len(result.stdout) > 262144:
            raise ValueError("DNS response too large")
        resolved = json.loads(result.stdout)
        if not isinstance(resolved, dict) or set(resolved) != set(hosts):
            raise ValueError("Invalid DNS response")
        for addresses in resolved.values():
            if not isinstance(addresses, list) or not 1 <= len(addresses) <= 256:
                raise ValueError("No valid IPv4 addresses")
            for address in addresses:
                if not isinstance(address, str):
                    raise ValueError("Invalid IPv4 address")
                ipaddress.IPv4Address(address)
        return resolved
    except (subprocess.SubprocessError, OSError, ValueError, TypeError) as exc:
        raise OSError("Backend IPv4 resolution failed") from exc


def validate_ip_family(value):
    if value not in {"auto", "ipv4"}:
        raise ValueError("GATEWAY_UPSTREAM_IP_FAMILY must be auto or ipv4")
    return value


def positive_env(name, default):
    value = float(os.getenv(name, default))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def endpoint(address, port):
    if not isinstance(address, str) or not address or len(address) > 253:
        raise ValueError("Invalid instance address")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid instance port")
    try:
        ip = ipaddress.ip_address(address)
        address = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                   for label in address.split(".")):
            raise ValueError("Invalid instance hostname") from None
    return f"{address}:{port}"


def parse_instances(payload, name, ip_family="auto", dns_timeout=2):
    validate_ip_family(ip_family)
    if not isinstance(payload, list) or len(payload) > 1000:
        raise ValueError("Invalid registry response")
    candidates = set()
    for item in payload:
        service = item["Service"]
        if service["Service"] != name:
            raise ValueError("Unexpected service name")
        checks = item["Checks"]
        if not isinstance(checks, list):
            raise ValueError("Invalid health checks")
        if any(check.get("Status") != "passing" for check in checks):
            continue
        address = service.get("Address") or item["Node"]["Address"]
        # Validate all registry input before using it in DNS or Nginx config.
        endpoint(address, service["Port"])
        candidates.add((address, service["Port"]))
    if ip_family == "auto":
        return sorted({endpoint(address, port) for address, port in candidates})
    result = set()
    hostnames = set()
    for address, port in candidates:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            hostnames.add(address)
        else:
            if ip.version == 4:
                result.add(endpoint(str(ip), port))
    resolved = resolve_ipv4(hostnames, dns_timeout)
    for address, port in candidates:
        for ip in resolved.get(address, []):
            result.add(endpoint(ip, port))
    return sorted(result)


class Discovery:
    def __init__(self, url, timeout=2, stale_ttl=15, token=None, clock=time.monotonic,
                 ip_family="auto", dns_timeout=2):
        if not url.startswith(("http://", "https://")):
            raise ValueError("CONSUL_URL must use HTTP(S)")
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.stale_ttl = stale_ttl
        self.token = token
        self.clock = clock
        self.cache = {}
        self.ip_family = validate_ip_family(ip_family)
        if not math.isfinite(dns_timeout) or not 0 < dns_timeout <= 10:
            raise ValueError("GATEWAY_DNS_TIMEOUT_SECONDS must be >0 and <=10")
        self.dns_timeout = dns_timeout

    def fetch(self, name):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["X-Consul-Token"] = self.token
        request = Request(f"{self.url}/v1/health/service/{name}?passing=true", headers=headers)
        with urlopen(request, timeout=self.timeout) as response:
            body = response.read(262145)
            if len(body) > 262144:
                raise ValueError("Registry response too large")
            return parse_instances(json.loads(body), name, self.ip_family, self.dns_timeout)

    def refresh_one(self, name):
        try:
            instances = self.fetch(name)
            self.cache[name] = (self.clock(), instances)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # Never log the registry URL, token or response body.
            LOG.warning("Registry lookup failed for %s", name)
        cached_at, instances = self.cache.get(name, (float("-inf"), []))
        return instances if self.clock() - cached_at < self.stale_ttl else []

    def refresh(self):
        names = list(ROUTES.values())
        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            return dict(zip(names, pool.map(self.refresh_one, names)))


def render(instances):
    lines = ["worker_processes auto;", "pid /var/run/nginx.pid;", "events {}", "http {",
             "log_format safe '$request_id $request_method $uri $status';",
             "access_log /dev/stdout safe;", "error_log /dev/stderr warn;"]
    for route, name in ROUTES.items():
        servers = instances.get(name, [])
        if servers:
            lines.append(f"upstream backend_{route} {{")
            lines.extend(f"server {server};" for server in servers)
            lines.append("}")
    lines.extend(["server {", "listen 80;", "server_name _;", "default_type application/json;",
                  "include /opt/gateway/docs/nginx-docs.conf;",
                  '''location = /health/ { return 200 '{"status":"ok","service":"api-gateway"}'; }''',
                  'error_page 502 504 =503 @unavailable;',
                  '''location @unavailable { return 503 '{"detail":"Service unavailable."}'; }''',
                  '''location = /auth/internal { return 404 '{"detail":"Not found."}'; }''',
                  '''location ^~ /auth/internal/ { return 404 '{"detail":"Not found."}'; }'''])
    for route, name in ROUTES.items():
        lines.append(f"location /{route}/ {{")
        if instances.get(name):
            lines.extend([f"proxy_pass http://backend_{route}/;", "proxy_http_version 1.1;",
                          "proxy_set_header Host $host;", "proxy_set_header Authorization $http_authorization;",
                          "proxy_set_header X-Request-ID $request_id;",
                          "proxy_set_header X-Real-IP $remote_addr;",
                          "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
                          "proxy_set_header X-Forwarded-Proto $scheme;",
                          "proxy_connect_timeout 2s;", "proxy_read_timeout 10s;",
                          "proxy_send_timeout 10s;", "proxy_next_upstream off;", "proxy_intercept_errors on;"])
        else:
            lines.append('''return 503 '{"detail":"Service unavailable."}';''')
        lines.append("}")
    lines.extend(['''location / { return 404 '{"detail":"Not found."}'; }''', "}", "}"])
    return "\n".join(lines) + "\n"


def apply_config(content, target=Path("/etc/nginx/nginx.conf"), reload=True):
    if target.exists() and target.read_text() == content:
        return False
    candidate = target.with_suffix(".candidate.conf")
    previous = target.read_text() if target.exists() else None
    try:
        candidate.write_text(content)
        subprocess.run(["nginx", "-t", "-c", str(candidate)], check=True,
                       capture_output=True, timeout=5)
        candidate.replace(target)
        if reload:
            subprocess.run(["nginx", "-s", "reload"], check=True, capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        if previous is not None:
            target.write_text(previous)
        raise
    finally:
        candidate.unlink(missing_ok=True)
    return True


def serve():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    discovery = Discovery(os.getenv("CONSUL_URL", "http://host.docker.internal:8500"),
                          positive_env("CONSUL_TIMEOUT_SECONDS", "2"),
                          positive_env("CONSUL_STALE_TTL_SECONDS", "15"), os.getenv("CONSUL_TOKEN"),
                          ip_family=os.getenv("GATEWAY_UPSTREAM_IP_FAMILY", "auto"),
                          dns_timeout=positive_env("GATEWAY_DNS_TIMEOUT_SECONDS", "2"))
    interval = positive_env("CONSUL_REFRESH_SECONDS", "3")
    stopping = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopping.set())
    # Fail-closed bootstrap is independent of registry availability.
    apply_config(render({}), reload=False)
    nginx = subprocess.Popen(["nginx", "-g", "daemon off;"])
    try:
        while not stopping.is_set() and nginx.poll() is None:
            if apply_config(render(discovery.refresh())):
                LOG.info("Healthy service routes updated")
            stopping.wait(interval)
        if not stopping.is_set():
            raise RuntimeError("Nginx exited unexpectedly")
    finally:
        # A failed reload terminates the container: stale routes cannot live forever.
        if nginx.poll() is None:
            nginx.send_signal(signal.SIGQUIT)
            try:
                nginx.wait(timeout=12)
            except subprocess.TimeoutExpired:
                nginx.kill()
                nginx.wait()


if __name__ == "__main__":
    serve()
