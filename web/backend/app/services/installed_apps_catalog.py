"""按平台汇总本机已连接设备及已安装应用列表（功能点分析）。"""

from __future__ import annotations

from app.schemas import (
    ConnectedDeviceOut,
    InstalledAppOut,
    InstalledAppsCatalogOut,
    PlatformInstalledCatalogItem,
)
from app.services.app_install import list_installed_apps
from app.services.device_discovery import list_connected_devices
from app.services.device_platform import DevicePlatform, normalize_device_platform
from app.services.package_platform import platform_label_cn


def build_installed_apps_catalog() -> InstalledAppsCatalogOut:
    """扫描鸿蒙 / Android 在线设备，分别拉取已安装应用供前端下拉选择。"""
    items: list[PlatformInstalledCatalogItem] = []

    for plat_key in ("harmonyos", "android"):
        plat: DevicePlatform = normalize_device_platform(plat_key)
        try:
            devices = list_connected_devices(plat)
        except RuntimeError as e:
            items.append(
                PlatformInstalledCatalogItem(
                    platform=plat,
                    platform_label=platform_label_cn(plat),
                    devices=[],
                    apps=[],
                    error=str(e),
                )
            )
            continue

        online = [d for d in devices if (d.state or "").lower() in ("device", "online")]
        if not online:
            continue

        device_outs = [
            ConnectedDeviceOut(device_id=d.device_id, label=d.label, state=d.state)
            for d in online
        ]
        primary = online[0]
        apps: list[InstalledAppOut] = []
        err = ""
        try:
            entries = list_installed_apps(plat, device_id=primary.device_id)
            apps = [
                InstalledAppOut(bundle_id=b, label=label)
                for b, label in entries
            ]
        except Exception as e:
            err = str(e)

        items.append(
            PlatformInstalledCatalogItem(
                platform=plat,
                platform_label=platform_label_cn(plat),
                devices=device_outs,
                apps=apps,
                error=err,
            )
        )

    return InstalledAppsCatalogOut(items=items)
