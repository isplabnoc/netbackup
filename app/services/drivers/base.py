from abc import ABC, abstractmethod
from pathlib import Path

from netmiko import ConnectHandler


class NetworkBackupDriver(ABC):
    device_type: str
    backup_command: str
    disable_paging_command: str | None = "terminal length 0"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        enable_secret: str | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
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
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "secret": self.enable_secret or "",
            "fast_cli": False,
            "conn_timeout": 30,
            "banner_timeout": 30,
            "session_timeout": 60,
        }
        self.connection = ConnectHandler(**params)
        if self.enable_secret and hasattr(self.connection, "enable"):
            self.connection.enable()

    def backup(self) -> str:
        if self.connection is None:
            raise RuntimeError("Connection not established")
        if self.disable_paging_command:
            try:
                self.connection.send_command(self.disable_paging_command, read_timeout=10)
            except Exception:
                pass
        config = str(self.connection.send_command(self.backup_command, read_timeout=300))
        header = (
            f"! Host: {self.host}\n"
            f"! Device Type: {self.device_type}\n"
            f"! Command: {self.backup_command}\n\n"
        )
        return f"{header}{config}"

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.disconnect()
            self.connection = None
