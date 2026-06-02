from app.services.drivers.base import NetmikoCommandDriver


class CiscoIOSDriver(NetmikoCommandDriver):
    device_type = "cisco_ios"
    backup_command = "show running-config"
