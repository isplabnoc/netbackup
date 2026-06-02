from app.models.device import Vendor
from app.services.drivers.base import NetworkBackupDriver
from app.services.drivers.cisco_ios import CiscoIOSDriver
from app.services.drivers.cisco_nxos import CiscoNXOSDriver
from app.services.drivers.dell_os10 import DellOS10Driver
from app.services.drivers.dell_os6 import DellOS6Driver
from app.services.drivers.f5_bigip import F5BigIPDriver
from app.services.drivers.fortigate import FortiGateDriver
from app.services.drivers.huawei_vrp import HuaweiVRPDriver
from app.services.drivers.juniper_junos import JuniperJunOSDriver
from app.services.drivers.mikrotik import MikroTikDriver

DRIVER_REGISTRY: dict[str, type[NetworkBackupDriver]] = {
    Vendor.dell_os6.value: DellOS6Driver,
    Vendor.dell_os10.value: DellOS10Driver,
    Vendor.mikrotik.value: MikroTikDriver,
    Vendor.cisco_ios.value: CiscoIOSDriver,
    Vendor.cisco_nxos.value: CiscoNXOSDriver,
    Vendor.fortigate.value: FortiGateDriver,
    Vendor.f5_bigip.value: F5BigIPDriver,
    Vendor.huawei_vrp.value: HuaweiVRPDriver,
    Vendor.juniper_junos.value: JuniperJunOSDriver,
}
