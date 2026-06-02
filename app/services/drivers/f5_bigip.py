from app.services.drivers.base import NetmikoCommandDriver


class F5BigIPDriver(NetmikoCommandDriver):
    device_type = "f5_tmsh"
    backup_command = "list"
