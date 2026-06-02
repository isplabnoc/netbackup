from app.services.drivers.base import NetmikoCommandDriver


class DellOS6Driver(NetmikoCommandDriver):
    device_type = "dell_powerconnect"
    backup_command = "show running-config"
