from abc import ABC, abstractmethod
from pathlib import Path

from netmiko import ConnectHandler


class NetworkBackupDriver(ABC):
    device_type: str
    backup_command: str

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        enable_secret: str | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.enable_secret = enable_secret
        self.output_dir = output_dir
        self.connection: object | None = None

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def backup(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError


class NetmikoCommandDriver(NetworkBackupDriver):
    def connect(self) -> None:
        params = {
            "device_type": self.device_type,
            "host": self.host,
            "username": self.username,
            "password": self.password,
            "secret": self.enable_secret or "",
        }
        self.connection = ConnectHandler(**params)
        if self.enable_secret and hasattr(self.connection, "enable"):
            self.connection.enable()

    def backup(self) -> str:
        if self.connection is None:
            raise RuntimeError("Connection not established")
        return str(self.connection.send_command(self.backup_command, read_timeout=120))

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.disconnect()
            self.connection = None
