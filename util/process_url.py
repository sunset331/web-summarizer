import hashlib
import os
import re
from typing import Optional, Tuple

from util.generate_summary import generate_summary
from util.save_to_markdown import save_to_markdown
from util.generate_tags import generate_content_tags
from util.organize_by_tags import organize_by_tags
from util.summary_xhs import summary_xhs
from util._save_raw_text import safe_filename


def _dispose_summarizer_browser(summarizer) -> None:
    drv = getattr(summarizer, "driver", None)
    if drv is None:
        return
    try:
        drv.quit()
    except Exception:
        pass
    try:
        summarizer.driver = None
    except Exception:
        pass


def _doubao_defaults() -> tuple[str, str]:
    from util.config_manager import get_doubao_config

    c = get_doubao_config()
    return (c.get("api_key") or "", c.get("model") or "")


def process_url(
    summarizer,
    url: str,
    api_key: str,
    model_name: str,
    output_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """api_key / model_name 为空时使用 config.json 中的豆包配置。

    返回 (摘要文本, 最终写入的 markdown 路径)；失败为 (None, None)。
    """
    if not (api_key or "").strip() or not (model_name or "").strip():
        dk, dm = _doubao_defaults()
        api_key = api_key or dk
        model_name = model_name or dm

    print(f"[INFO] 开始处理: {url}")

    work_dir: Optional[str] = None
    if output_path:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.basename(output_path)
        if base.lower() in ("summary.md", "summary"):
            domain = re.sub(r"[^a-zA-Z0-9]", "_", url.split("//")[-1].split("/")[0])
            path_hash = hashlib.md5(url.encode()).hexdigest()[:6]
            output_name = safe_filename(f"{domain}_{path_hash}_summary.md")
            output_path = os.path.join(out_dir, output_name)
        else:
            output_path = os.path.abspath(output_path)
        work_dir = out_dir

    try:
        if "xiaohongshu.com" in url or "xhslink.com" in url:
            result = summarizer.fetch_web_content(url, work_dir=work_dir)
        else:
            result = summarizer.fetch_web_content(url)

        if not result or not result[0]:
            print("[ERROR] 内容获取失败: 未能提取到网页正文")
            return None, None

        if len(result) == 3:
            raw_content, dir, img_paths = result
        else:
            raw_content, dir = result
            img_paths = []

        print(f"[INFO] 获取内容成功, 长度: {len(raw_content)}字符")

        if "xiaohongshu.com" in url or "xhslink.com" in url:
            summary = summary_xhs(raw_content, img_paths, api_key, model_name)
        else:
            summary = generate_summary(raw_content, api_key, model_name)
        print(f"[INFO] 摘要生成完成, 长度: {len(summary)}字符")

        print("[INFO] 正在生成内容标签...")
        try:
            tags = generate_content_tags(raw_content, api_key, model_name)
            print("[INFO] 标签生成完成")
            print(f"[INFO] 生成的标签: {tags}")
        except Exception as e:
            print(f"[ERROR] 标签生成失败: {str(e)}")
            tags = {"content_tags": [], "user_purpose": []}

        if not output_path:
            domain = re.sub(r"[^a-zA-Z0-9]", "_", url.split("//")[-1].split("/")[0])
            path_hash = hashlib.md5(url.encode()).hexdigest()[:6]
            output_name = safe_filename(f"{domain}_{path_hash}_summary.md")
            output_path = os.path.join(dir, output_name)

        save_to_markdown(url, summary, output_path, model_name, tags)

        print("[INFO] 正在按标签整理文件...")
        organize_by_tags(output_path, tags)

        return summary, output_path
    finally:
        _dispose_summarizer_browser(summarizer)
