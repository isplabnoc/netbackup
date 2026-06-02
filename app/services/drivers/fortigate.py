from app.services.drivers.base import NetmikoCommandDriver


class FortiGateDriver(NetmikoCommandDriver):
    device_type = "fortinet"
    backup_command = "show full-configuration"
