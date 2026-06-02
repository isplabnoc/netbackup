from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.device import Device
from app.services.credential import CredentialService
from app.services.drivers import DRIVER_REGISTRY


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    message: str


class ConnectionTestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.credentials = CredentialService(db)

    def test_device(self, device: Device) -> ConnectionTestResult:
        try:
            credential = device.credential
            password, enable_secret = self.credentials.reveal(credential)
            driver_cls = DRIVER_REGISTRY[device.vendor]
            driver = driver_cls(
                host=device.ip,
                username=credential.username,
                password=password,
                enable_secret=enable_secret,
            )
            try:
                driver.connect()
            finally:
                driver.disconnect()
            return ConnectionTestResult(True, "Conexao SSH realizada com sucesso")
        except Exception as exc:
            return ConnectionTestResult(False, str(exc))
