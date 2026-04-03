import json
import unittest
from urllib.parse import parse_qs, urlparse

from scripts.n8n_client import N8nClient, N8nConfig


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class RecordingSession:
    def __init__(self, payload=None):
        self.payload = payload if payload is not None else {"data": []}
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(self.payload)

    def patch(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {"method": "PATCH", "url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeResponse(self.payload)

    def put(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {"method": "PUT", "url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeResponse(self.payload)


class N8nClientTests(unittest.TestCase):
    def test_list_workflows_builds_expected_query_and_auth_header(self):
        session = RecordingSession({"data": [{"id": "wf-1"}]})
        client = N8nClient(
            N8nConfig(base_url="https://example.n8n.cloud/", api_key="secret-key"),
            session=session,
        )

        payload = client.list_workflows(active=True, tags=["ops", "prod"], limit=25)

        self.assertEqual(payload["data"][0]["id"], "wf-1")
        self.assertEqual(len(session.calls), 1)
        parsed = urlparse(session.calls[0]["url"])
        self.assertEqual(parsed.path, "/api/v1/workflows")
        query = parse_qs(parsed.query)
        self.assertEqual(query["active"], ["true"])
        self.assertEqual(query["tags"], ["ops,prod"])
        self.assertEqual(query["limit"], ["25"])
        self.assertEqual(
            session.calls[0]["headers"]["X-N8N-API-KEY"],
            "secret-key",
        )

    def test_get_execution_can_request_summary_only(self):
        session = RecordingSession({"id": "123"})
        client = N8nClient(
            N8nConfig(base_url="https://example.n8n.cloud", api_key="secret-key"),
            session=session,
        )

        client.get_execution("123", include_data=False)

        parsed = urlparse(session.calls[0]["url"])
        self.assertEqual(parsed.path, "/api/v1/executions/123")
        query = parse_qs(parsed.query)
        self.assertEqual(query["includeData"], ["false"])

    def test_health_check_uses_workflows_endpoint_with_minimal_limit(self):
        session = RecordingSession({"data": []})
        client = N8nClient(
            N8nConfig(base_url="https://example.n8n.cloud", api_key="secret-key"),
            session=session,
        )

        status = client.health_check()

        self.assertEqual(status["ok"], True)
        parsed = urlparse(session.calls[0]["url"])
        self.assertEqual(parsed.path, "/api/v1/workflows")
        self.assertEqual(parse_qs(parsed.query)["limit"], ["1"])

    def test_update_workflow_uses_put_with_json_body(self):
        session = RecordingSession({"id": "wf-1", "name": "Updated"})
        client = N8nClient(
            N8nConfig(base_url="https://example.n8n.cloud", api_key="secret-key"),
            session=session,
        )

        workflow = {"name": "Updated", "nodes": [], "connections": {}, "settings": {}}
        payload = client.update_workflow("wf-1", workflow)

        self.assertEqual(payload["id"], "wf-1")
        self.assertEqual(session.calls[0]["method"], "PUT")
        self.assertEqual(session.calls[0]["json"], workflow)
        self.assertEqual(urlparse(session.calls[0]["url"]).path, "/api/v1/workflows/wf-1")

    def test_rename_workflow_fetches_and_updates_name_only(self):
        session = RecordingSession({"id": "wf-1", "name": "Renamed"})
        client = N8nClient(
            N8nConfig(base_url="https://example.n8n.cloud", api_key="secret-key"),
            session=session,
        )

        # first GET returns current workflow, second call is PUT response
        session.payload = {
            "id": "wf-1",
            "name": "Original",
            "nodes": [],
            "connections": {},
            "settings": {},
        }

        original_write = client._write

        def fake_write(method, path, payload):
            session.calls.append({"method": method.upper(), "url": client._build_url(path), "json": payload})
            return {"id": "wf-1", **payload}

        client._write = fake_write
        try:
            payload = client.rename_workflow("wf-1", "Renamed")
        finally:
            client._write = original_write

        self.assertEqual(payload["name"], "Renamed")
        self.assertEqual(session.calls[-1]["method"], "PUT")
        self.assertEqual(session.calls[-1]["json"]["name"], "Renamed")

    def test_prepare_workflow_for_update_strips_read_only_fields(self):
        workflow = {
            "id": "wf-1",
            "name": "Updated",
            "nodes": [],
            "connections": {},
            "settings": {
                "executionOrder": "v1",
                "errorWorkflow": "abc123",
                "callerPolicy": "workflowsFromSameOwner",
                "availableInMCP": True,
                "timeSavedMode": "fixed",
            },
            "staticData": {"x": 1},
            "pinData": {"Manual Trigger": []},
            "versionId": "abc",
            "active": True,
        }

        prepared = N8nClient.prepare_workflow_for_update(workflow)

        self.assertEqual(
            prepared,
            {
                "name": "Updated",
                "nodes": [],
                "connections": {},
                "settings": {
                    "executionOrder": "v1",
                    "errorWorkflow": "abc123",
                },
                "staticData": {"x": 1},
                "pinData": {"Manual Trigger": []},
            },
        )


if __name__ == "__main__":
    unittest.main()
