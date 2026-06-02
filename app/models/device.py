from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class Vendor(StrEnum):
    dell_os6 = "Dell OS6"
    dell_os10 = "Dell OS10"
    mikrotik = "MikroTik"
    cisco_ios = "Cisco IOS"
    cisco_nxos = "Cisco NXOS"
    fortigate = "FortiGate"
    f5_bigip = "F5 BIG-IP"
    huawei_vrp = "Huawei VRP"
    juniper_junos = "Juniper JunOS"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    vendor: Mapped[str] = mapped_column(String(80), index=True)
    platform: Mapped[str] = mapped_column(String(120))
    credential_group_id: Mapped[int] = mapped_column(ForeignKey("credentials.id"))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credential = relationship("Credential", back_populates="devices")
    backups = relationship("Backup", back_populates="device", cascade="all, delete-orphan")
    diffs = relationship("Diff", back_populates="device", cascade="all, delete-orphan")
