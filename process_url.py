import os
import re
import hashlib
from util.generate_summary import generate_summary
from util.save_to_markdown import save_to_markdown
from util.generate_tags import generate_content_tags
from util.organize_by_tags import organize_by_tags
from typing import Optional
from util.summary_xhs import summary_xhs
from util._save_raw_text import safe_filename

def process_url(summarizer, url: str, api_key: str, model_name: str, output_path: Optional[str] = None):
    print(f"[INFO] 开始处理: {url}")
    result = summarizer.fetch_web_content(url)
    if not result or not result[0]:
        print(f"[ERROR] 内容获取失败: 未能提取到网页正文")
        return None
    
    # 处理返回值，兼容不同Summarizer的返回格式
    if len(result) == 3:  # 小红书：返回 (content, save_dir, img_paths)
        raw_content, dir, img_paths = result
    else:  # 其他平台：返回 (content, save_dir)
        raw_content, dir = result
        img_paths = []
    
    print(f"[INFO] 获取内容成功, 长度: {len(raw_content)}字符")
    
    # 生成摘要
    if "xiaohongshu.com" in url or "xhslink.com" in url:
        summary = summary_xhs(raw_content, img_paths, api_key, model_name)
    else:
        summary = generate_summary(raw_content, api_key, model_name)
    print(f"[INFO] 摘要生成完成, 长度: {len(summary)}字符")
    
    # 生成标签
    print("[INFO] 正在生成内容标签...")
    try:
        tags = generate_content_tags(raw_content, api_key, model_name)
        print(f"[INFO] 标签生成完成")
        print(f"[INFO] 生成的标签: {tags}")
    except Exception as e:
        print(f"[ERROR] 标签生成失败: {str(e)}")
        tags = {"content_tags": [], "user_purpose": []}
    
    if not output_path:     
        domain = re.sub(r'[^a-zA-Z0-9]', '_', url.split('//')[-1].split('/')[0])
        path_hash = hashlib.md5(url.encode()).hexdigest()[:6]
        # 保留中文，去除emoji
        output_name = safe_filename(f"{domain}_{path_hash}_summary.md")
        output_path = os.path.join(dir, output_name)
    
    # 保存包含标签的Markdown文件
    save_to_markdown(url, summary, output_path, model_name, tags)
    
    # 按标签整理文件
    print("[INFO] 正在按标签整理文件...")
    organize_by_tags(output_path, tags)
    
    return summary 