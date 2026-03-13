from datetime import datetime
from typing import Optional, Dict, Any

def save_to_markdown(url: str, summary: str, output_path: str, model_name: str, tags: Optional[Dict[str, Any]] = None):
    """
    保存摘要到Markdown文件，包含标签信息
    
    Args:
        url: 源URL
        summary: 生成的摘要
        output_path: 输出文件路径
        model_name: 使用的模型名称
        tags: 标签字典，包含content_tags和user_purpose
    """
    # 处理标签信息
    content_tags_str = ""
    user_purpose_str = ""
    
    print(f"[INFO] 接收到的标签: {tags}")
    
    if tags:
        content_tags = tags.get("content_tags", [])
        user_purpose = tags.get("user_purpose", [])
        
        print(f"[INFO] 内容标签: {content_tags}")
        print(f"[INFO] 用户目的: {user_purpose}")
        
        if content_tags:
            content_tags_str = f"**内容标签**: {', '.join(content_tags)}\n\n"
        if user_purpose:
            user_purpose_str = f"**记录目的**: {', '.join(user_purpose)}\n\n"
    
    md_content = f"""# 网页内容摘要

**源URL**: [{url}]({url})

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

**模型**: {model_name}

{content_tags_str}{user_purpose_str}---

{summary}
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"[INFO] 摘要已保存至: {output_path}")
    
    # 打印标签信息
    if tags:
        print(f"[INFO] 内容标签: {', '.join(tags.get('content_tags', []))}")
        print(f"[INFO] 记录目的: {', '.join(tags.get('user_purpose', []))}") 