from app.services.drivers.base import NetmikoCommandDriver


class CiscoNXOSDriver(NetmikoCommandDriver):
    device_type = "cisco_nxos"
    backup_command = "show running-config"
