"""Minimal Neon API client for branching and connection lifecycle management."""

from __future__ import annotations

import httpx
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(slots=True)
class NeonAPICredentials:
    """Credential bundle used for Neon API calls."""

    api_key: str
    project_id: str
    base_url: str = "https://console.neon.tech/api/v2"


class NeonAPIClient:
    """Thin wrapper around Neon REST endpoints used during provisioning."""

    def __init__(self, credentials: NeonAPICredentials, *, timeout: float = 10.0) -> None:
        self._creds = credentials
        self._timeout = timeout

    # ------------------------------------------------------------------
    def create_branch(self, source_branch_id: str, name: str) -> Dict[str, Any]:
        payload = {"branch": {"name": name, "parent_id": source_branch_id}}
        return self._post(f"/projects/{self._creds.project_id}/branches", payload)

    def delete_branch(self, branch_id: str) -> Dict[str, Any]:
        return self._delete(f"/projects/{self._creds.project_id}/branches/{branch_id}")

    def issue_connection_uri(self, branch_id: str) -> str:
        response = self._post(
            f"/projects/{self._creds.project_id}/branches/{branch_id}/connection_uri",
            payload={},
        )
        return response["connection_uri"]

    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._creds.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout, headers=self._headers()) as client:
            response = client.post(self._creds.base_url + path, json=payload)
            response.raise_for_status()
            return response.json()

    def _delete(self, path: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout, headers=self._headers()) as client:
            response = client.delete(self._creds.base_url + path)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {"status": "deleted"}
