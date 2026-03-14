"""
Edge 驱动版本检测模块

仅检测本机 Edge 浏览器版本与本地 msedgedriver 版本是否一致。
若不一致或未找到本地驱动，不进行自动下载，仅给出手动下载并替换的流程提示并中止运行。
"""

import os
import re
import subprocess
import sys

# Windows 下隐藏子进程窗口
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Windows 上 Edge 的常见安装路径
EDGE_PATHS_WIN = [
    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
]

# 本地驱动搜索路径（按优先级）
def _local_driver_search_paths():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [
        os.path.join(root, "msedgedriver.exe"),
        os.path.join(os.getcwd(), "msedgedriver.exe"),
        r"D:\edgedriver_win64\msedgedriver.exe",
        "msedgedriver.exe",  # PATH
    ]


def _get_edge_version_from_registry():
    """从 Windows 注册表读取 Edge 版本（不依赖执行 msedge.exe）。"""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Edge\BLBeacon",
            0,
            winreg.KEY_READ,
        )
        version, _ = winreg.QueryValueEx(key, "version")
        winreg.CloseKey(key)
        if version and re.match(r"^\d+\.\d+\.\d+", str(version)):
            return str(version).strip()
    except (OSError, FileNotFoundError, Exception):
        pass
    return None


def get_edge_browser_version():
    """
    获取本机安装的 Microsoft Edge 浏览器版本号。
    先尝试注册表（Windows），再尝试执行 msedge --version。

    Returns:
        str: 版本号，如 "145.0.3800.97"；获取失败返回 None。
    """
    if sys.platform == "win32":
        ver = _get_edge_version_from_registry()
        if ver:
            return ver

    paths_to_try = EDGE_PATHS_WIN
    if sys.platform != "win32":
        paths_to_try = ["/usr/bin/microsoft-edge", "/usr/bin/msedge"]

    for exe_path in paths_to_try:
        if not exe_path or not os.path.isfile(exe_path):
            continue
        try:
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            out = (result.stdout or result.stderr or "").strip()
            if result.returncode == 0 and out:
                match = re.search(r"(\d+\.\d+\.\d+\.?\d*)", out)
                if match:
                    return match.group(1)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            continue
    return None


def find_local_driver_path():
    """
    在本地常见位置查找 msedgedriver 可执行文件。

    Returns:
        str | None: 找到的驱动完整路径，未找到返回 None。
    """
    for path in _local_driver_search_paths():
        try:
            if path == "msedgedriver.exe":
                which = _which("msedgedriver.exe")
                if which:
                    return which
                continue
            if os.path.isfile(path):
                return os.path.abspath(path)
        except Exception:
            continue
    return None


def _which(name):
    """在 PATH 中查找可执行文件路径。"""
    try:
        import shutil
        return shutil.which(name)
    except Exception:
        return None


def get_driver_version(driver_path):
    """
    通过执行 msedgedriver --version 获取驱动版本号。

    Args:
        driver_path: msedgedriver.exe 的路径（可为 PATH 中的名字）。

    Returns:
        str | None: 版本号，如 "139.0.2704.0"；获取失败返回 None。
    """
    if not driver_path:
        return None
    try:
        use_shell = driver_path == "msedgedriver.exe" or os.path.basename(driver_path) == "msedgedriver.exe"
        result = subprocess.run(
            [driver_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=use_shell and sys.platform == "win32",
            creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode != 0:
            return None
        out = (result.stdout or result.stderr or "").strip()
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
        if match:
            return match.group(1)
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
        if match:
            return ".".join(match.groups())
    except Exception:
        pass
    return None


def get_major_version(version_str):
    """从版本串中取主版本号，如 '145.0.3800.97' -> 145。"""
    if not version_str:
        return None
    try:
        return int(str(version_str).strip().split(".")[0])
    except (ValueError, IndexError):
        return None


def versions_match(browser_version, driver_version):
    """
    判断浏览器主版本与驱动主版本是否一致（Edge 要求主版本一致才能用）。

    Returns:
        bool: 主版本号相同返回 True。
    """
    if not browser_version or not driver_version:
        return False
    try:
        b_main = int(browser_version.split(".")[0])
        d_main = int(driver_version.split(".")[0])
        return b_main == d_main
    except (ValueError, IndexError):
        return False


def _print_manual_download_instructions(browser_version, driver_version, local_path, missing_driver=False):
    """打印手动下载并替换的流程提示。"""
    major = get_major_version(browser_version) if browser_version else None
    print()
    print("=" * 60)
    print("  Edge 驱动版本与浏览器不一致，请手动下载并替换后重试")
    print("=" * 60)
    if browser_version:
        print(f"  本机 Edge 浏览器版本: {browser_version}")
        if major is not None:
            print(f"  需要匹配的驱动主版本: {major}（下载时请选择该版本）")
    if local_path and driver_version:
        print(f"  当前本地驱动路径: {local_path}")
        print(f"  当前本地驱动版本: {driver_version}")
    if missing_driver:
        print("  未检测到本地 msedgedriver，请先下载并放置到指定目录。")
    print()
    print("  手动操作步骤：")
    print("  1. 打开下载页面：")
    print("     https://developer.microsoft.com/zh-cn/microsoft-edge/tools/webdriver/")
    print("  2. 选择与当前 Edge 主版本一致的驱动（如 " + (str(major) if major is not None else "xxx") + "），选择 Windows 平台并下载。")
    print("  3. 解压得到 msedgedriver.exe，替换到以下位置之一：")
    print("     - 项目根目录（web_summarizer 目录下）")
    print("     - D:\\edgedriver_win64\\")
    print("  4. 重新运行本程序。")
    print("=" * 60)
    print()


def ensure_edge_driver():
    """
    检测本机 Edge 与本地 msedgedriver 版本是否一致。
    - 一致则返回本地驱动路径，供调用方使用。
    - 不一致或未找到本地驱动时，打印手动下载并替换的流程提示，并抛出 RuntimeError 中止运行（不进行自动下载）。
    """
    browser_version = get_edge_browser_version()
    if not browser_version:
        print("[ERROR] 无法检测到本机 Edge 浏览器版本。")
        _print_manual_download_instructions(None, None, None, missing_driver=True)
        raise RuntimeError("无法检测 Edge 版本，请确保已安装 Microsoft Edge，或手动将匹配的 msedgedriver 放入项目目录或 D:\\edgedriver_win64\\")

    print(f"[INFO] 本机 Edge 浏览器版本: {browser_version}")

    local_path = find_local_driver_path()
    if not local_path:
        print("[ERROR] 未找到本地 Edge 驱动（msedgedriver.exe）。")
        _print_manual_download_instructions(browser_version, None, None, missing_driver=True)
        raise RuntimeError("未找到本地 msedgedriver，请按上述步骤下载并放置后重试。")

    driver_version = get_driver_version(local_path)
    if not driver_version:
        print("[ERROR] 无法读取本地驱动版本。")
        _print_manual_download_instructions(browser_version, None, local_path, missing_driver=False)
        raise RuntimeError("无法读取本地驱动版本，请按上述步骤下载并替换后重试。")

    print(f"[INFO] 本地 Edge 驱动路径: {local_path}，版本: {driver_version}")

    if not versions_match(browser_version, driver_version):
        print("[ERROR] 浏览器与驱动版本不一致，程序中止。请按以下提示手动下载并替换驱动。")
        _print_manual_download_instructions(browser_version, driver_version, local_path, missing_driver=False)
        raise RuntimeError("Edge 驱动版本与浏览器不一致，请按上述步骤下载并替换后重试。")

    print("[INFO] 浏览器与驱动版本一致，使用本地驱动。")
    return local_path
