"""Documentation contract checks without importing services or querying their databases."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "api-gateway" / "docs"
SPEC = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
METHODS = {"get", "post", "put", "patch", "delete"}
sys.path.insert(0, str(ROOT / "api-gateway"))
from discovery import render


def module_ast(root, module):
    return ast.parse((root / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8-sig"))


def imports(tree, module):
    result = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            base = module.split(".")[:-node.level] if node.level else []
            if node.module:
                base += node.module.split(".")
            for alias in node.names:
                result[alias.asname or alias.name] = (".".join(base), alias.name)
    return result


def class_fields(root, module, name):
    tree = module_ast(root, module)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    result = set()
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in classes:
            result |= class_fields(root, module, base.id)
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            result.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return result


def view_methods(root, module, name):
    tree = module_ast(root, module)
    node = next(n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    if isinstance(node, ast.FunctionDef):
        return {"get"}  # The only function-based public routes here are health checks.
    result = {n.name for n in node.body if isinstance(n, ast.FunctionDef) and n.name in METHODS}
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in classes:
            result |= view_methods(root, module, base.id)
    return result


def published_routes(root, module="config.urls", prefix=""):
    tree = module_ast(root, module)
    imported = imports(tree, module)
    result = {}

    def value(expr, env):
        if isinstance(expr, ast.Constant):
            return expr.value
        if isinstance(expr, ast.Name):
            return env[expr.id]
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            return value(expr.left, env) + value(expr.right, env)
        raise AssertionError("Unsupported route expression; update the contract inventory test")

    def visit(nodes, env):
        for node in nodes:
            if isinstance(node, ast.For):
                for item in ast.literal_eval(node.iter):
                    names = [node.target.id] if isinstance(node.target, ast.Name) else [n.id for n in node.target.elts]
                    values = [item] if len(names) == 1 else item
                    visit(node.body, {**env, **dict(zip(names, values))})
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "path":
                    continue
                route = prefix + value(call.args[0], env)
                target = call.args[1]
                if route.startswith(("internal/", "admin/")):
                    continue
                if isinstance(target, ast.Call) and isinstance(target.func, ast.Name) and target.func.id == "include":
                    result.update(published_routes(root, value(target.args[0], env), route))
                    continue
                if isinstance(target, ast.Call):
                    name = target.func.value.id
                else:
                    name = target.id
                view_module, view_name = imported[name]
                methods = view_methods(root, view_module, view_name)
                # CompositeView uses one class for collection/detail; only these bindings are callable.
                if view_name in {"StudentProfileView", "LecturerProfileView"}:
                    methods &= {"get", "patch", "delete"} if "<" in route else {"get", "post"}
                path = "/" + re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)
                result[path] = methods
    visit(tree.body, {})
    return result


class OpenAPIContractTests(unittest.TestCase):
    def test_openapi_semantic_validation(self):
        try:
            from openapi_spec_validator import validate
        except ImportError:
            self.skipTest("Install api-gateway/tests/requirements-docs.txt for semantic validation")
        validate(SPEC)

    def test_request_examples_satisfy_their_documented_schemas(self):
        try:
            from openapi_schema_validator import OAS30WriteValidator
        except ImportError:
            self.skipTest("Install documentation validation tooling for example validation")
        for name, schema in SPEC["components"]["schemas"].items():
            if "example" in schema:
                with self.subTest(schema=name):
                    document = {"$ref": "#/components/schemas/" + name,
                                "components": SPEC["components"]}
                    OAS30WriteValidator(document).validate(schema["example"])

    def test_routes_and_methods_match_service_sources(self):
        expected = {"/health/": {"get"}}
        for service, prefix in [("auth-service", "auth"), ("academic-services", "academic"),
                                ("regist-service", "registrations"), ("topic-service", "topics")]:
            for path, methods in published_routes(ROOT / "services" / service).items():
                expected["/" + prefix + path] = methods
        self.assertEqual({path: set(ops) for path, ops in SPEC["paths"].items()}, expected)

    def test_dto_fields_match_sources_including_inherited_fields(self):
        for name, schema in SPEC["components"]["schemas"].items():
            source = schema.get("x-dto-source")
            if not source:
                continue
            service = next(service for prefix, service in [
                ("Auth", "auth-service"), ("Academic", "academic-services"),
                ("Regist", "regist-service"), ("Topic", "topic-service")] if name.startswith(prefix))
            with self.subTest(schema=name):
                self.assertEqual(set(schema["properties"]), class_fields(
                    ROOT / "services" / service, source["module"], source["class"]))

    def test_refs_parameters_operation_ids_and_security(self):
        ids = []
        for path, methods in SPEC["paths"].items():
            self.assertNotIn("internal", path)
            self.assertNotIn("admin", path)
            for method, operation in methods.items():
                with self.subTest(path=path, method=method):
                    ids.append(operation["operationId"])
                    self.assertEqual(set(re.findall(r"\{([^}]+)\}", path)), {
                        p["name"] for p in operation.get("parameters", []) if p["in"] == "path" and p["required"]})
                    public = path.endswith("/health/") or path in {"/auth/login/", "/auth/token/refresh/"}
                    self.assertEqual(operation.get("security", SPEC["security"]), [] if public else [{"BearerAuth": []}])
                    self.assertIn("503", operation["responses"])
                    if "204" in operation["responses"]:
                        self.assertNotIn("content", operation["responses"]["204"])
        self.assertEqual(len(ids), len(set(ids)))

        def walk(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    self.assertTrue(value["$ref"].startswith("#/"))
                    target = SPEC
                    for part in value["$ref"][2:].split("/"):
                        target = target[part.replace("~1", "/").replace("~0", "~")]
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(SPEC)

    def test_patch_contracts_and_sensitive_fields(self):
        schemas = SPEC["components"]["schemas"]
        for name, schema in schemas.items():
            if name.endswith("Patch"):
                self.assertNotIn("required", schema)
        self.assertNotIn("password", schemas["AuthUserResponseSerializer"]["properties"])
        self.assertNotIn("password", schemas["AcademicProfileOutput"]["properties"])
        self.assertEqual(schemas["AcademicProfileInput"]["properties"]["password"]["writeOnly"], True)
        self.assertNotIn("put", SPEC["paths"]["/academic/api/v1/students/{pk}/"])
        self.assertIn("role 2", SPEC["paths"]["/topics/api/v1/topics/"]["get"]["description"])
        self.assertIn("Admin role 1 only", SPEC["paths"]["/registrations/api/v1/topics/{topic_id}/registrations/"]["delete"]["description"])

    def test_ui_is_local_and_does_not_persist_tokens_or_validate_remotely(self):
        self.assertEqual(SPEC["servers"], [{"url": "/", "description": "Current API Gateway origin"}])
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        for url in re.findall(r'(?:src|href)="([^"]+)"', html):
            if url.startswith("data:"):
                continue
            self.assertTrue(url.startswith("/swagger/"))
            self.assertTrue((DOCS / url.removeprefix("/swagger/")).is_file())
        config = (DOCS / "swagger-config.js").read_text(encoding="utf-8")
        for setting in ["url: '/openapi.json'", "persistAuthorization: false", "queryConfigEnabled: false",
                        "validatorUrl: null", "withCredentials: false", "tryItOutEnabled: false"]:
            self.assertIn(setting, config)
        self.assertNotRegex(config, r"https?://")

    def test_vendored_assets_match_pinned_release_manifest(self):
        manifest = json.loads((DOCS / "vendor" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "5.33.1")
        for name, record in manifest["files"].items():
            self.assertTrue(record["source"].startswith("https://raw.githubusercontent.com/swagger-api/swagger-ui/v5.33.1/"))
            self.assertEqual(hashlib.sha256((DOCS / "vendor" / name).read_bytes()).hexdigest(), record["sha256"])

    def test_bootstrap_and_discovery_share_documentation_locations(self):
        for config in [(ROOT / "api-gateway" / "nginx.conf").read_text(encoding="utf-8"),
                       render({}), render({"auth-service": ["127.0.0.1:8001"]})]:
            self.assertEqual(config.count("include /opt/gateway/docs/nginx-docs.conf;"), 1)
            self.assertIn("location ^~ /auth/internal/ { return 404", config)
            self.assertIn("location / { return 404", config)


if __name__ == "__main__":
    unittest.main()
