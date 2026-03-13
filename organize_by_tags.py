import os
from datetime import datetime
from typing import Dict, Any, Optional

def organize_by_tags(md_path: str, tags: Dict[str, Any], base_dir: Optional[str] = None) -> None:
    """
    根据标签整理文件，使用索引文件方案
    
    Args:
        md_path: Markdown文件的完整路径
        tags: 标签字典，包含content_tags和user_purpose
        base_dir: 基础目录，默认为桌面
    """
    if not tags:
        print("没有标签信息，跳过整理")
        return
    
    # 设置基础目录
    if base_dir is None:
        base_dir = os.path.join(os.path.expanduser("~"), "Desktop", "标签整理")
    
    # 确保基础目录存在
    os.makedirs(base_dir, exist_ok=True)
    
    # 获取文件名（不含路径）
    file_name = os.path.basename(md_path)
    file_name_without_ext = os.path.splitext(file_name)[0]
    
    # 处理内容标签
    content_tags = tags.get("content_tags", [])
    for tag in content_tags:
        if tag.strip():  # 确保标签不为空
            _update_tag_index(base_dir, tag, md_path, file_name, file_name_without_ext)
    
    # 处理用户目的标签
    user_purposes = tags.get("user_purpose", [])
    for purpose in user_purposes:
        if purpose.strip():  # 确保目的不为空
            _update_tag_index(base_dir, purpose, md_path, file_name, file_name_without_ext)
    
    print(f"文件已按标签整理到: {base_dir}")

def _update_tag_index(base_dir: str, tag: str, md_path: str, file_name: str, file_name_without_ext: str) -> None:
    """
    更新特定标签的索引文件
    
    Args:
        base_dir: 基础目录
        tag: 标签名称
        md_path: Markdown文件路径
        file_name: 文件名
        file_name_without_ext: 不含扩展名的文件名
    """
    # 创建标签目录
    tag_dir = os.path.join(base_dir, tag)
    os.makedirs(tag_dir, exist_ok=True)
    
    # 索引文件路径
    index_file = os.path.join(tag_dir, "index.md")
    
    # 使用绝对路径指向原始文件
    abs_path = os.path.abspath(md_path)
    # 转换为file://协议格式，确保在Markdown中能正确打开
    rel_path = f"file:///{abs_path.replace('\\', '/')}"
    
    # 读取现有索引文件
    existing_entries = []
    if os.path.exists(index_file):
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单的解析，查找已有的文件条目
                lines = content.split('\n')
                for line in lines:
                    if line.strip().startswith('- [') and '](' in line:
                        existing_entries.append(line.strip())
        except Exception as e:
            print(f"[ERROR] 读取索引文件失败: {e}")
    
    # 检查文件是否已经在索引中
    file_entry = f"- [{file_name_without_ext}]({rel_path})"
    if file_entry not in existing_entries:
        # 添加新条目
        existing_entries.append(file_entry)
        
        # 写入索引文件
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(f"# {tag} 相关文档\n\n")
                f.write(f"**标签**: {tag}\n")
                f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**文档数量**: {len(existing_entries)}\n\n")
                f.write("## 文档列表\n\n")
                
                # 按文件名排序
                existing_entries.sort()
                for entry in existing_entries:
                    f.write(f"{entry}\n")
                
                f.write(f"\n---\n")
                f.write(f"*此索引文件由网页摘要工具自动生成*\n")
            
            print(f"[INFO] 已更新标签 '{tag}' 的索引文件")
        except Exception as e:
            print(f"[ERROR] 写入索引文件失败: {e}")

def create_main_index(base_dir: Optional[str] = None) -> None:
    """
    创建主索引文件，显示所有标签
    
    Args:
        base_dir: 基础目录
    """
    if base_dir is None:
        base_dir = os.path.join(os.path.expanduser("~"), "Desktop", "标签整理")
    
    if not os.path.exists(base_dir):
        print("[ERROR] 标签整理目录不存在")
        return
    
    main_index_file = os.path.join(base_dir, "README.md")
    
    try:
        # 获取所有标签目录
        tag_dirs = []
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path) and item != "__pycache__":
                tag_dirs.append(item)
        
        # 按标签名称排序
        tag_dirs.sort()
        
        with open(main_index_file, 'w', encoding='utf-8') as f:
            f.write("# 标签整理目录\n\n")
            f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**标签总数**: {len(tag_dirs)}\n\n")
            f.write("## 标签列表\n\n")
            
            for tag in tag_dirs:
                index_path = os.path.join(tag, "index.md")
                f.write(f"- [{tag}](./{index_path})\n")
            
            f.write(f"\n---\n")
            f.write(f"*此索引文件由网页摘要工具自动生成*\n")
        
        print(f"[INFO] 主索引文件已创建: {main_index_file}")
    except Exception as e:
        print(f"[ERROR] 创建主索引文件失败: {e}")

def get_tag_statistics(base_dir: Optional[str] = None) -> Dict[str, int]:
    """
    获取标签统计信息
    
    Args:
        base_dir: 基础目录
    
    Returns:
        标签统计字典
    """
    if base_dir is None:
        base_dir = os.path.join(os.path.expanduser("~"), "Desktop", "标签整理")
    
    if not os.path.exists(base_dir):
        return {}
    
    stats = {}
    try:
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path) and item != "__pycache__":
                index_file = os.path.join(item_path, "index.md")
                if os.path.exists(index_file):
                    # 简单统计文档数量
                    with open(index_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 计算文档列表中的条目数
                        doc_count = content.count('- [')
                        stats[item] = doc_count
    except Exception as e:
        print(f"[ERROR] 获取标签统计失败: {e}")
    
    return stats 