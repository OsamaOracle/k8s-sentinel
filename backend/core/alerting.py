"""Slack and Teams alerting for Kubernetes Sentinel anomalies."""

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AlertManager:
    """Sends anomaly alerts to Slack and/or Microsoft Teams via webhooks."""

    def __init__(self) -> None:
        self.slack_url: str | None = os.environ.get("SLACK_WEBHOOK_URL") or None
        self.teams_url: str | None = os.environ.get("TEAMS_WEBHOOK_URL") or None
        self.cooldown: int = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "300"))
        self._last_alerted: dict[str, float] = {}

    def _anomaly_key(self, anomaly: dict[str, Any]) -> str:
        return (
            f"{anomaly.get('namespace', '')}:"
            f"{anomaly.get('label', '')}:"
            f"{(anomaly.get('detail') or '')[:60]}"
        )

    async def send_slack(self, anomaly: dict[str, Any]) -> None:
        """POST an anomaly alert to the configured Slack webhook."""
        if not self.slack_url:
            return
        sev = anomaly.get("sev", "med")
        namespace = anomaly.get("namespace") or "—"
        label = anomaly.get("label", "Unknown")
        detail = anomaly.get("detail") or ""
        payload = {
            "text": "Kubernetes Sentinel Alert",
            "attachments": [
                {
                    "color": "danger" if sev == "high" else "warning",
                    "title": label,
                    "fields": [
                        {"title": "Namespace", "value": namespace, "short": True},
                        {"title": "Severity", "value": sev.upper(), "short": True},
                        {"title": "Detail", "value": detail, "short": False},
                    ],
                    "footer": "Kubernetes Sentinel",
                    "ts": int(time.time()),
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.slack_url, json=payload)
                resp.raise_for_status()
            logger.info("Slack alert sent for anomaly: %s", label)
        except Exception:
            logger.exception("Failed to send Slack alert for anomaly: %s", label)

    async def send_teams(self, anomaly: dict[str, Any]) -> None:
        """POST an anomaly alert to the configured Teams webhook."""
        if not self.teams_url:
            return
        sev = anomaly.get("sev", "med")
        namespace = anomaly.get("namespace") or "—"
        label = anomaly.get("label", "Unknown")
        detail = anomaly.get("detail") or ""
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "Kubernetes Sentinel Alert",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "Rule", "value": label},
                                    {"title": "Namespace", "value": namespace},
                                    {"title": "Severity", "value": sev.upper()},
                                    {"title": "Detail", "value": detail},
                                ],
                            },
                        ],
                    },
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.teams_url, json=payload)
                resp.raise_for_status()
            logger.info("Teams alert sent for anomaly: %s", label)
        except Exception:
            logger.exception("Failed to send Teams alert for anomaly: %s", label)

    async def maybe_alert(self, anomaly: dict[str, Any]) -> None:
        """Send alerts for an anomaly if cooldown has elapsed and channels are configured."""
        if not self.slack_url and not self.teams_url:
            return
        key = self._anomaly_key(anomaly)
        now = time.time()
        if now - self._last_alerted.get(key, 0) < self.cooldown:
            return
        self._last_alerted[key] = now
        if self.slack_url:
            await self.send_slack(anomaly)
        if self.teams_url:
            await self.send_teams(anomaly)
