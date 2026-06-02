from app.services.drivers.base import NetmikoCommandDriver


class JuniperJunOSDriver(NetmikoCommandDriver):
    device_type = "juniper_junos"
    backup_command = "show configuration | display set"
