from pathlib import Path

import paramiko
from netmiko import ConnectHandler

from app.services.drivers.base import NetworkBackupDriver


class MikroTikDriver(NetworkBackupDriver):
    device_type = "mikrotik_routeros"

    def connect(self) -> None:
        self.connection = ConnectHandler(
            device_type=self.device_type,
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            fast_cli=False,
            conn_timeout=30,
            banner_timeout=30,
            session_timeout=60,
        )

    def backup(self) -> str:
        if self.connection is None:
            raise RuntimeError("Connection not established")
        export = str(self.connection.send_command("/export show-sensitive", read_timeout=120))
        backup_name = "netaudit.backup"
        self.connection.send_command(f"/system backup save name={backup_name}", read_timeout=120)
        self._download_backup_file(backup_name)
        return export

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.disconnect()
            self.connection = None

    def _download_backup_file(self, backup_name: str) -> None:
        if self.output_dir is None:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        local_path = self.output_dir / backup_name
        transport = paramiko.Transport((self.host, self.port))
        try:
            transport.connect(username=self.username, password=self.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            try:
                sftp.get(backup_name, str(local_path))
            finally:
                sftp.close()
        finally:
            transport.close()
