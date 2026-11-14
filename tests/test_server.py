import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from tessera import api as api_module

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = api_module.demo_api()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                         api_module.handler_for(cls.api))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path, token="demo-token"):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())


class TestOverRealHttp(ServerCase):
    def test_health_is_open(self):
        status, body = self.get("/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_a_request_without_a_token_is_401(self):
        status, body = self.get("/v1/objects/Contact", token=None)
        self.assertEqual(status, 401)

    def test_a_wrong_token_is_401(self):
        status, _ = self.get("/v1/objects/Contact", token="nope")
        self.assertEqual(status, 401)

    def test_the_object_list_answers(self):
        status, body = self.get("/v1/objects/Contact")
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "Contact")
        self.assertEqual(len(body["ids"]), 1, "the demo projection is built")

    def test_the_unified_view_answers(self):
        status, body = self.get(
            "/v1/mesh/view/Contact/018f0000-0000-7000-8000-00000000c001")
        self.assertEqual(status, 200)
        self.assertIn("email", body["fields"])

    def test_an_unknown_route_is_404(self):
        status, _ = self.get("/nope")
        self.assertEqual(status, 404)

    def test_the_handler_is_reusable(self):
        self.assertTrue(callable(api_module.handler_for(self.api)))


class TestDeploymentArtefacts(unittest.TestCase):
    def test_the_dockerfile_runs_as_a_non_root_user(self):
        text = read("Dockerfile")
        self.assertIn("FROM python:3.12-slim", text)
        self.assertIn("USER 10001", text)
        self.assertNotIn("USER root", text)

    def test_the_dockerfile_has_a_real_healthcheck(self):
        text = read("Dockerfile")
        self.assertIn("HEALTHCHECK", text)
        self.assertIn("/health", text)

    def test_the_image_has_no_baked_credential(self):
        for path in ("Dockerfile", "docker-compose.yml", "deploy/k8s.yaml"):
            text = read(path)
            self.assertNotIn("TESSERA_TOKEN=secret", text)
        self.assertIn("replace-me", read("deploy/k8s.yaml"),
                      "the manifest carries a placeholder that says so")

    def test_the_entrypoint_is_the_module(self):
        self.assertIn('ENTRYPOINT ["python3", "-m", "tessera.api"]', read("Dockerfile"))

    def test_the_yaml_parses_and_is_hardened(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed; the structural checks need it")

        compose = yaml.safe_load(read("docker-compose.yml"))
        service = compose["services"]["tessera"]
        self.assertTrue(service["read_only"])
        self.assertIn("ALL", service["cap_drop"])
        self.assertIn("no-new-privileges:true", service["security_opt"])
        self.assertIn("healthcheck", service)

        manifests = list(yaml.safe_load_all(read("deploy/k8s.yaml")))
        kinds = [m["kind"] for m in manifests]
        self.assertEqual(kinds, ["Namespace", "ConfigMap", "Secret", "Deployment",
                                 "Service"])

        deployment = [m for m in manifests if m["kind"] == "Deployment"][0]
        pod = deployment["spec"]["template"]["spec"]
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        container = pod["containers"][0]
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/health")
        self.assertEqual(container["livenessProbe"]["httpGet"]["path"], "/health")
        self.assertIn("limits", container["resources"])

    def test_the_manifest_and_compose_agree_on_the_image(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed")
        compose_image = yaml.safe_load(read("docker-compose.yml"))["services"]["tessera"]["image"]
        manifests = list(yaml.safe_load_all(read("deploy/k8s.yaml")))
        deployment = [m for m in manifests if m["kind"] == "Deployment"][0]
        self.assertEqual(deployment["spec"]["template"]["spec"]["containers"][0]["image"],
                         compose_image)


if __name__ == "__main__":
    unittest.main()
