from app.services.drivers.base import NetmikoCommandDriver


class HuaweiVRPDriver(NetmikoCommandDriver):
    device_type = "huawei"
    backup_command = "display current-configuration"
