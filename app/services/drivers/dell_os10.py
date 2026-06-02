from app.services.drivers.base import NetmikoCommandDriver


class DellOS10Driver(NetmikoCommandDriver):
    device_type = "dell_os10"
    backup_command = "show running-configuration"
