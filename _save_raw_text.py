import os
from datetime import datetime
import re
import base64

def safe_filename(s):
    """保留中文，去除emoji和特殊符号"""
    def is_valid_char(c):
        # 保留中文
        if '\u4e00' <= c <= '\u9fff':
            return True
        # 保留英文、数字、下划线、点、横线
        if re.match(r'[A-Za-z0-9._-]', c):
            return True
        # 去除emoji和其他特殊符号
        return False
    return ''.join(c for c in s if is_valid_char(c))

def image_to_base64(image_path):
    """将图片转换为Base64编码，仅支持JPG/JPEG/PNG/BMP"""
    try:
        ext = os.path.splitext(image_path)[-1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.bmp']:
            print(f"[警告] 不支持的图片格式: {ext}，仅支持JPG/JPEG/PNG/BMP")
            return None
        with open(image_path, 'rb') as f:
            image_data = f.read()
        if ext == '.jpg' or ext == '.jpeg':
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.bmp':
            mime_type = 'image/bmp'
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        print(f"[警告] 图片转Base64失败: {str(e)}")
        return None

def _save_raw_text(content: str, url: str, save_path):
    try:
        domain = re.sub(r'\W+', '_', url.split('//')[-1].split('/')[0])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 保留中文，去除emoji
        filename = safe_filename(f"raw_{domain}_{timestamp}.txt")
        output_path = os.path.join(save_path, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"URL: {url}\n")
            f.write(f"Saved at: {datetime.now()}\n\n")
            f.write(content if content else "NULL_CONTENT")
        print(f"[INFO] 原始文本已保存到桌面: {output_path}")
        print(f"[INFO] 保存路径: {os.path.abspath(output_path)}")
    except Exception as e:
        print(f"[ERROR] 原始文本保存失败: {str(e)}") 