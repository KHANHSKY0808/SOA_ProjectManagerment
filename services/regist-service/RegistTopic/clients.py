"""Bounded REST clients with healthy-instance discovery and failure circuits."""
import ipaddress
import json
import logging
import re
import threading
import time
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from rest_framework.exceptions import APIException, NotFound, PermissionDenied


LOG = logging.getLogger(__name__)


class DependencyUnavailable(APIException):
    status_code = 503
    default_detail = "Registration reference services are temporarily unavailable."
    default_code = "dependency_unavailable"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_json(url, headers, timeout, data=None):
    headers = {"Accept": "application/json", **headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Oversized response")
        return json.loads(raw)


def instance_url(address, port):
    if not isinstance(address, str) or not address or len(address) > 253:
        raise ValueError("Invalid service address")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid service port")
    try:
        ip = ipaddress.ip_address(address)
        address = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                   for part in address.split(".")):
            raise ValueError("Invalid hostname") from None
    return f"http://{address}:{port}"


def valid_id(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 255


class ReferenceClient:
    def __init__(self, service, setting):
        self.service, self.setting = service, setting
        self.failures, self.open_until = 0, 0
        self.lock = threading.Lock()

    def base_url(self, config):
        if not config["DISCOVERY_ENABLED"]:
            base = config["BASE_URL"].rstrip("/")
            parsed = urlsplit(base)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Invalid development URL")
            return base
        consul = settings.CONSUL
        headers = {"X-Consul-Token": consul["TOKEN"]} if consul.get("TOKEN") else {}
        instances = fetch_json(consul["URL"].rstrip("/") + f"/v1/health/service/{self.service}?passing=true",
                               headers, config["TIMEOUT_SECONDS"])
        if not isinstance(instances, list):
            raise ValueError("Invalid registry response")
        for item in instances:
            service, checks = item["Service"], item["Checks"]
            if service["Service"] != self.service or not isinstance(checks, list):
                raise ValueError("Invalid service instance")
            if checks and all(check["Status"] == "passing" for check in checks):
                return instance_url(service.get("Address") or item["Node"]["Address"], service["Port"])
        raise ValueError("No healthy instances")

    def call(self, path, authorization, request_id, validate, data=None, missing=None):
        config = getattr(settings, self.setting)
        # Log operation names only: paths/queries can contain student-selected IDs.
        operation = ("student_names" if path == "/api/v1/student-display-names/" else
                     "context" if path == "/api/v1/registration-context/" else
                     "departments" if path == "/api/v1/major-departments/" else
                     "topic_page" if path.startswith("/api/v1/registration-topics/?") else "topic_detail")
        correlation = request_id if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", request_id) else "invalid"
        with self.lock:
            if time.monotonic() < self.open_until:
                LOG.warning("Reference lookup unavailable service=%s operation=%s stage=circuit request_id=%s",
                            self.service, operation, correlation)
                raise DependencyUnavailable()
        stage = "discovery"
        try:
            base = self.base_url(config)
            stage = "request"
            try:
                result = fetch_json(base + path, {"Authorization": authorization, "X-Request-ID": request_id},
                                    config["TIMEOUT_SECONDS"], data)
            except HTTPError as exc:
                if missing and exc.code == missing[0]:
                    with self.lock:
                        self.failures, self.open_until = 0, 0
                    raise missing[1] from None
                raise
            stage = "validation"
            validate(result)
        except (OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError) as exc:
            LOG.warning("Reference lookup failed service=%s operation=%s stage=%s error=%s upstream_status=%s request_id=%s",
                        self.service, operation, stage, type(exc).__name__,
                        exc.code if isinstance(exc, HTTPError) else "none", correlation)
            with self.lock:
                self.failures += 1
                if self.failures >= 3:
                    self.open_until = time.monotonic() + 10
            raise DependencyUnavailable() from None
        with self.lock:
            self.failures, self.open_until = 0, 0
        return result


class AcademicClient(ReferenceClient):
    def student_names(self, student_ids, authorization, request_id):
        ids = list(dict.fromkeys(student_ids))
        def validate(payload):
            names = payload["student_names"]
            if (not isinstance(names, dict) or set(names) != set(ids)
                    or any(value is not None and not isinstance(value, str) for value in names.values())
                    or type(payload.get("names_unavailable")) is not bool):
                raise ValueError("Invalid student names DTO")
        return self.call("/api/v1/student-display-names/", authorization, request_id,
                         validate, {"student_ids": ids})

    def context(self, identity, authorization, request_id):
        def validate(payload):
            if not isinstance(payload, dict) or payload.get("student_id") != identity or not valid_id(payload.get("department_id")):
                raise ValueError("Invalid student context")
        return self.call("/api/v1/registration-context/", authorization, request_id, validate,
                         missing=(403, PermissionDenied("Student has no valid faculty.")))

    def departments(self, major_ids, authorization, request_id):
        ids = list(dict.fromkeys(major_ids))
        if len(ids) > 100:
            raise DependencyUnavailable()
        def validate(payload):
            values = payload["departments"]
            if not isinstance(values, dict) or set(values) != set(ids) or any(
                    value is not None and not valid_id(value) for value in values.values()):
                raise ValueError("Invalid faculty references")
        return self.call("/api/v1/major-departments/", authorization, request_id, validate,
                         {"major_ids": ids})["departments"]


def validate_topic(payload):
    if not isinstance(payload, dict) or not all(valid_id(payload.get(key)) for key in ("topic_id", "major_id")):
        raise ValueError("Invalid topic references")
    if "status" not in payload or not isinstance(payload.get("name"), str) or not (payload.get("status") is None or type(payload.get("status")) is int):
        raise ValueError("Invalid topic DTO")


class TopicClient(ReferenceClient):
    def management_topic(self, topic_id, authorization, request_id):
        def validate(payload):
            if (not isinstance(payload, dict) or payload.get("topic_id") != topic_id or "advisor_id" not in payload
                    or not (payload.get("advisor_id") is None or valid_id(payload.get("advisor_id")))
                    or "status" not in payload or not (payload["status"] is None or type(payload["status"]) is int)):
                raise ValueError("Invalid topic ownership DTO")
        return self.call("/api/v1/topics/" + quote(topic_id, safe="") + "/",
                         authorization, request_id, validate, missing=(404, NotFound("Topic not found.")))

    def topic(self, topic_id, authorization, request_id):
        def validate(payload):
            validate_topic(payload)
            if payload["topic_id"] != topic_id:
                raise ValueError("Wrong topic")
        return self.call("/api/v1/registration-topics/" + quote(topic_id, safe="") + "/",
                         authorization, request_id, validate, missing=(404, NotFound("Topic not found.")))

    def page(self, after, authorization, request_id):
        def validate(payload):
            rows, cursor = payload["results"], payload["next_after"]
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError("Invalid topic page")
            previous = after
            for row in rows:
                validate_topic(row)
                if row["status"] != 2 or row["topic_id"] <= previous:
                    raise ValueError("Invalid topic order/status")
                previous = row["topic_id"]
            if cursor is not None and (not rows or len(rows) != 100 or cursor != previous):
                raise ValueError("Invalid page cursor")
        return self.call("/api/v1/registration-topics/?after=" + quote(after, safe=""),
                         authorization, request_id, validate)


academic_client = AcademicClient("academic-service", "ACADEMIC_CLIENT")
topic_client = TopicClient("topic-service", "TOPIC_CLIENT")
