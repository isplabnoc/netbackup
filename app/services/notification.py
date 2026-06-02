import http.client
import json
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.core.logging import app_logger
from app.services.settings import AppSettingsService


@dataclass(frozen=True)
class BackupSummary:
    total: int
    success: int
    failed: int
    failed_devices: list[str]


@dataclass(frozen=True)
class NotificationResult:
    channel: str
    success: bool
    message: str
    status_code: int | None = None


class NotificationService:
    def __init__(self, settings: Settings | None = None, config: dict[str, str | None] | None = None) -> None:
        self.settings = settings or get_settings()
        self.config = config or {}

    @classmethod
    def from_db(cls, settings_service: AppSettingsService) -> "NotificationService":
        return cls(config=settings_service.notification_config())

    def send_backup_summary(self, summary: BackupSummary) -> None:
        message = (
            "Resumo de backup\n"
            f"Total: {summary.total}\n"
            f"Sucesso: {summary.success}\n"
            f"Falhas: {summary.failed}\n"
            f"Dispositivos com erro: {', '.join(summary.failed_devices) or 'nenhum'}"
        )
        try:
            self.send_telegram(message)
            self.send_evolution(message)
        except Exception:
            app_logger.exception("notification_delivery_failed")

    def send_test(self) -> list[NotificationResult]:
        return [
            self.send_telegram("NetBackup Pro: teste de notificacao Telegram"),
            self.send_evolution("NetBackup Pro: teste de notificacao Evolution API"),
        ]

    def send_telegram(self, message: str) -> NotificationResult:
        bot_token = self.config.get("telegram_bot_token") or self.settings.telegram_bot_token
        chat_id = self.config.get("telegram_chat_id") or self.settings.telegram_chat_id
        if not bot_token or not chat_id:
            return NotificationResult("telegram", False, "Telegram nao configurado.")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        return self._post_json("telegram", url, {"chat_id": chat_id, "text": message})

    def send_evolution(self, message: str) -> NotificationResult:
        api_url = self.config.get("evolution_api_url") or self.settings.evolution_api_url
        api_token = self.config.get("evolution_api_token") or self.settings.evolution_api_token
        instance = self.config.get("evolution_api_instance") or self.settings.evolution_api_instance
        recipient = self.config.get("evolution_api_recipient")
        if not api_url or not api_token or not instance or not recipient:
            return NotificationResult("evolution", False, "Evolution API nao configurada completamente.")
        url = f"{api_url.rstrip('/')}/message/sendText/{instance}"
        return self._post_json(
            "evolution",
            url,
            {"number": recipient, "text": message},
            headers={"apikey": api_token},
        )

    def _post_json(
        self,
        channel: str,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> NotificationResult:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return NotificationResult(channel, False, "URL invalida.")
        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.netloc, timeout=10)
        try:
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            body = json.dumps(payload)
            conn.request("POST", path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
            response = conn.getresponse()
            response_body = response.read().decode("utf-8", errors="replace")
            if response.status >= 300:
                app_logger.warning("notification_failed", extra={"url": url, "status": response.status})
                return NotificationResult(channel, False, response_body or "Falha no envio.", response.status)
            return NotificationResult(channel, True, "Mensagem enviada com sucesso.", response.status)
        except OSError as exc:
            app_logger.warning("notification_connection_failed", extra={"channel": channel, "error": str(exc)})
            return NotificationResult(channel, False, str(exc))
        finally:
            conn.close()
