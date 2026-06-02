import http.client
import json
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.core.logging import app_logger


@dataclass(frozen=True)
class BackupSummary:
    total: int
    success: int
    failed: int
    failed_devices: list[str]


class NotificationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send_backup_summary(self, summary: BackupSummary) -> None:
        message = (
            "Resumo de backup\n"
            f"Total: {summary.total}\n"
            f"Sucesso: {summary.success}\n"
            f"Falhas: {summary.failed}\n"
            f"Dispositivos com erro: {', '.join(summary.failed_devices) or 'nenhum'}"
        )
        try:
            self._send_telegram(message)
            self._send_evolution(message)
        except Exception:
            app_logger.exception("notification_delivery_failed")

    def _post_json(self, url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> None:
        parsed = urlparse(url)
        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.netloc, timeout=10)
        try:
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            body = json.dumps(payload)
            conn.request("POST", path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
            response = conn.getresponse()
            response.read()
            if response.status >= 300:
                app_logger.warning("notification_failed", extra={"url": url, "status": response.status})
        finally:
            conn.close()

    def _send_telegram(self, message: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        self._post_json(url, {"chat_id": self.settings.telegram_chat_id, "text": message})

    def _send_evolution(self, message: str) -> None:
        if (
            not self.settings.evolution_api_url
            or not self.settings.evolution_api_token
            or not self.settings.evolution_api_instance
        ):
            return
        url = (
            f"{self.settings.evolution_api_url.rstrip('/')}/message/sendText/"
            f"{self.settings.evolution_api_instance}"
        )
        self._post_json(
            url,
            {"text": message},
            headers={"apikey": self.settings.evolution_api_token},
        )
