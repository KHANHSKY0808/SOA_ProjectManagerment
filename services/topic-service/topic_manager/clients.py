"""Bounded academic REST validation without shared ORM or static fallback."""
import ipaddress
import json
import re
import threading
import time
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError


class DependencyUnavailable(APIException):
    status_code = 503
    default_detail = "Academic validation is temporarily unavailable."
    default_code = "dependency_unavailable"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer token to a redirected host.


def fetch_json(url, headers, timeout, data=None):
    headers = {"Accept": "application/json", **headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(262145)
        if len(body) > 262144:
            raise ValueError("Oversized response")
        return json.loads(body)


def instance_url(address, port):
    if not isinstance(address, str) or not address or len(address) > 253:
        raise ValueError("Invalid address")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    try:
        ip = ipaddress.ip_address(address)
        address = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                   for part in address.split(".")):
            raise ValueError("Invalid hostname") from None
    return f"http://{address}:{port}"


class AcademicClient:
    def __init__(self):
        self.failures = 0
        self.open_until = 0
        self.lock = threading.Lock()

    def base_url(self, config, service_name="academic-service"):
        if not config["DISCOVERY_ENABLED"]:
            base = config["BASE_URL"].rstrip("/")
            parsed = urlsplit(base)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
                raise ValueError("Invalid development URL")
            return base
        consul = settings.CONSUL
        headers = {"X-Consul-Token": consul["TOKEN"]} if consul.get("TOKEN") else {}
        instances = fetch_json(consul["URL"].rstrip("/") + f"/v1/health/service/{service_name}?passing=true",
                               headers, config["TIMEOUT_SECONDS"])
        if not isinstance(instances, list) or not instances:
            raise ValueError("No healthy instances")
        for item in instances:
            service = item["Service"]
            checks = item["Checks"]
            if service["Service"] != service_name or not isinstance(checks, list) or not checks:
                raise ValueError("Invalid registry payload")
            if all(check["Status"] == "passing" for check in checks):
                return instance_url(service.get("Address") or item["Node"]["Address"], service["Port"])
        raise ValueError("No healthy instances")

    def validate(self, references, authorization):
        config = settings.ACADEMIC_CLIENT
        # Validate unsupported IDs before consulting the circuit or registry.
        for field, resource, key, value in references:
            if resource == "majors" and not re.fullmatch(r"[0-9]+", value):
                raise ValidationError({field: "Academic major lookup currently requires a numeric ID."})
        with self.lock:
            if time.monotonic() < self.open_until:
                raise DependencyUnavailable()
        try:
            base = self.base_url(config)
            for field, resource, key, value in references:
                try:
                    payload = fetch_json(f"{base}/api/{resource}/{quote(value, safe='')}/",
                                         {"Authorization": authorization}, config["TIMEOUT_SECONDS"])
                except HTTPError as exc:
                    if exc.code == 404:
                        raise ValidationError({field: "Referenced academic record does not exist."}) from None
                    raise
                if not isinstance(payload, dict) or str(payload.get(key)) != value:
                    raise ValueError("Invalid academic DTO")
        except ValidationError:
            with self.lock:
                self.failures = 0
                self.open_until = 0
            raise
        except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
            with self.lock:
                self.failures += 1
                if self.failures >= config["FAILURE_THRESHOLD"]:
                    self.open_until = time.monotonic() + config["COOLDOWN_SECONDS"]
            raise DependencyUnavailable() from None
        with self.lock:
            self.failures = 0
            self.open_until = 0

    def display_names(self, major_ids, advisor_ids, authorization):
        config = settings.ACADEMIC_CLIENT
        majors = list(dict.fromkeys(major_ids))
        advisors = list(dict.fromkeys(advisor_ids))
        result = {"major_names": dict.fromkeys(majors), "advisor_names": dict.fromkeys(advisors)}
        if not majors and not advisors:
            return result
        with self.lock:
            if time.monotonic() < self.open_until:
                raise DependencyUnavailable()
        try:
            base = self.base_url(config)
            for start in range(0, max(len(majors), len(advisors)), 100):
                batch = {"major_ids": majors[start:start + 100], "advisor_ids": advisors[start:start + 100]}
                payload = fetch_json(base + "/api/v1/topic-display-names/",
                                     {"Authorization": authorization}, config["TIMEOUT_SECONDS"], batch)
                for field, id_field in (("major_names", "major_ids"), ("advisor_names", "advisor_ids")):
                    names = payload[field]
                    if not isinstance(names, dict) or set(names) != set(batch[id_field]) or any(
                            value is not None and not isinstance(value, str) for value in names.values()):
                        raise ValueError("Invalid academic name DTO")
                    result[field].update(names)
        except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
            with self.lock:
                self.failures += 1
                if self.failures >= config["FAILURE_THRESHOLD"]:
                    self.open_until = time.monotonic() + config["COOLDOWN_SECONDS"]
            raise DependencyUnavailable() from None
        with self.lock:
            self.failures = 0
            self.open_until = 0
        return result


academic_client = AcademicClient()
# Display-only failures must not open the mandatory write-validation circuit.
academic_names_client = AcademicClient()


class RegistrationCleanupClient(AcademicClient):
    """One bounded DELETE; never retry or redirect forwarded credentials."""
    def purge(self, topic_id, authorization, request_id):
        config = settings.REGISTRATION_CLIENT
        try:
            base = self.base_url(config, "regist-service")
            request = Request(base + "/api/v1/topics/" + quote(topic_id, safe="") + "/registrations/",
                              method="DELETE", headers={"Authorization": authorization,
                              "X-Request-ID": request_id, "Accept": "application/json"})
            with build_opener(NoRedirect()).open(request, timeout=config["TIMEOUT_SECONDS"]) as response:
                body = response.read(4097)
                if response.status != 200 or len(body) > 4096:
                    raise ValueError("Invalid cleanup response")
                payload = json.loads(body)
                if (not isinstance(payload, dict) or payload.get("topic_id") != topic_id
                        or type(payload.get("deleted_count")) is not int or payload["deleted_count"] < 0):
                    raise ValueError("Invalid cleanup DTO")
                return payload["deleted_count"]
        except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
            raise DependencyUnavailable("Registration cleanup could not be confirmed.") from None


registration_cleanup_client = RegistrationCleanupClient()
