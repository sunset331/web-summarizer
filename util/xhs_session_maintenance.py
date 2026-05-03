"""
小红书专用 Edge user-data-dir 的 Cookie 定期清理。

Chromium/Edge 将站点 Cookie 存在 SQLite 文件中；在浏览器未占用该目录时删除这些文件，
可强制下次访问重新登录。间隔默认 3 天，可通过环境变量 XHS_COOKIE_CLEAR_INTERVAL_DAYS 修改。
"""

from __future__ import annotations

import json
import os
import time

STATE_FILENAME = ".xhs_cookie_maintenance.json"

# 相对 user-data-dir 根目录的常见 Cookie 存储路径（新版 Default/Network/Cookies + 旧版）
_COOKIE_REL_PATHS: tuple[tuple[str, ...], ...] = (
    ("Default", "Network", "Cookies"),
    ("Default", "Network", "Cookies-journal"),
    ("Default", "Cookies"),
    ("Default", "Cookies-journal"),
)


def get_cookie_clear_interval_days() -> float:
    raw = os.environ.get("XHS_COOKIE_CLEAR_INTERVAL_DAYS", "").strip()
    if raw:
        try:
            v = float(raw)
            if v > 0:
                return v
        except ValueError:
            pass
    return 3.0


def _safe_remove_file(path: str) -> bool:
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True
    except OSError:
        return False
    return False


def _remove_chromium_cookie_db_files(profile_dir: str) -> int:
    removed = 0
    for parts in _COOKIE_REL_PATHS:
        p = os.path.join(profile_dir, *parts)
        if _safe_remove_file(p):
            removed += 1
    return removed


def maybe_clear_expired_xhs_session(profile_dir: str) -> bool:
    """
    若距离上次记录已超过间隔天数，则删除该 profile 下的 Chromium Cookie 库文件并更新时间戳。
    若尚无状态文件（首次在本机使用本逻辑），只写入当前时间，不删除已有 Cookie。

    Returns:
        本次是否执行了删除（删除了至少一个文件）则为 True。
    """
    interval_sec = get_cookie_clear_interval_days() * 86400.0
    os.makedirs(profile_dir, exist_ok=True)
    state_path = os.path.join(profile_dir, STATE_FILENAME)
    now = time.time()
    last_clear: float | None = None

    if os.path.isfile(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_clear = float(data.get("last_cookie_clear_epoch", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            last_clear = None

    if last_clear is None:
        try:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"last_cookie_clear_epoch": now}, f)
        except OSError:
            pass
        return False

    if (now - last_clear) < interval_sec:
        return False

    n = _remove_chromium_cookie_db_files(profile_dir)
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"last_cookie_clear_epoch": now}, f)
    except OSError:
        pass

    days = get_cookie_clear_interval_days()
    if n > 0:
        print(
            f"[INFO] 小红书自动化配置目录已超过 {days:g} 天，已删除 Cookie 数据库文件（{n} 个），"
            "下次抓取前请在「手动登录」流程中重新登录。"
        )
    else:
        print(
            f"[INFO] 小红书自动化配置目录已超过 {days:g} 天，已刷新维护时间；"
            "未找到 Cookie 文件（可能尚未生成或路径与当前 Edge 版本不一致）。"
        )
    return n > 0
