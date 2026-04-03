from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests


DEFAULT_TIMEOUT_SECONDS = 20
UPDATE_WORKFLOW_ALLOWED_FIELDS = (
    "name",
    "nodes",
    "connections",
    "settings",
    "staticData",
    "pinData",
)
UPDATE_WORKFLOW_ALLOWED_SETTINGS = (
    "timezone",
    "saveDataErrorExecution",
    "saveDataSuccessExecution",
    "saveManualExecutions",
    "saveExecutionProgress",
    "executionTimeout",
    "errorWorkflow",
    "executionOrder",
)


@dataclass(frozen=True)
class N8nConfig:
    base_url: str
    api_key: str
    api_version: str = "v1"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


class N8nClient:
    def __init__(self, config: N8nConfig, session: requests.Session | Any | None = None):
        self.config = config
        self.session = session or requests.Session()

    def list_workflows(
        self,
        *,
        active: bool | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if active is not None:
            params["active"] = str(active).lower()
        if tags:
            params["tags"] = ",".join(tags)
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        return self._get("workflows", params)

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._get(f"workflows/{workflow_id}")

    def list_executions(
        self,
        *,
        workflow_id: str | None = None,
        status: str | None = None,
        include_data: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"includeData": str(include_data).lower()}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        return self._get("executions", params)

    def get_execution(self, execution_id: str, include_data: bool = True) -> dict[str, Any]:
        return self._get(
            f"executions/{execution_id}",
            {"includeData": str(include_data).lower()},
        )

    def health_check(self) -> dict[str, Any]:
        self._get("workflows", {"limit": 1})
        return {
            "ok": True,
            "baseUrl": self.config.normalized_base_url,
            "apiVersion": self.config.api_version,
        }

    def update_workflow(self, workflow_id: str, workflow: dict[str, Any]) -> dict[str, Any]:
        return self._write(
            "put",
            f"workflows/{workflow_id}",
            self.prepare_workflow_for_update(workflow),
        )

    def rename_workflow(self, workflow_id: str, new_name: str) -> dict[str, Any]:
        current = self.get_workflow(workflow_id)
        current["name"] = new_name
        return self.update_workflow(workflow_id, current)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._build_url(path, params)
        response = self.session.get(
            url,
            headers={"X-N8N-API-KEY": self.config.api_key},
            timeout=self.config.timeout_seconds,
        )
        self._raise_for_status(response)
        return response.json()

    def _write(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._build_url(path)
        request_method = getattr(self.session, method.lower())
        response = request_method(
            url,
            headers={"X-N8N-API-KEY": self.config.api_key},
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        self._raise_for_status(response)
        return response.json()

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        base = f"{self.config.normalized_base_url}/api/{self.config.api_version}/{path.lstrip('/')}"
        if not params:
            return base
        return f"{base}?{urlencode(params)}"

    def _raise_for_status(self, response: Any) -> None:
        try:
            response.raise_for_status()
        except Exception as exc:
            detail = getattr(response, "text", "")
            if detail:
                raise RuntimeError(f"{exc} | response={detail}") from exc
            raise

    @staticmethod
    def prepare_workflow_for_update(workflow: dict[str, Any]) -> dict[str, Any]:
        prepared = {
            key: workflow[key]
            for key in UPDATE_WORKFLOW_ALLOWED_FIELDS
            if key in workflow
        }
        for required_key in ("name", "nodes", "connections", "settings"):
            if required_key not in prepared:
                raise ValueError(
                    f"Workflow update payload is missing required field: {required_key}"
                )
        prepared["settings"] = {
            key: prepared["settings"][key]
            for key in UPDATE_WORKFLOW_ALLOWED_SETTINGS
            if key in prepared["settings"]
        }
        return prepared
