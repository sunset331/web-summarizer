import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from util._save_raw_text import _save_raw_text
from base import BaseSummarizer

class ElsepageSummarizer(BaseSummarizer):
    def fetch_web_content(self, url: str):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://www.google.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Connection': 'keep-alive',
            'DNT': '1'
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup(['header', 'footer', 'nav', 'aside', 'script', 'style']):
                element.decompose()
            domain = re.sub(r'[^a-zA-Z0-9]', '_', url.split('//')[-1].split('/')[0])
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            folder_name = f"{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            save_dir = os.path.join(desktop, folder_name)
            os.makedirs(save_dir, exist_ok=True)
            main_content = (soup.find('main') or 
                            soup.find('article') or 
                            soup.find('div', class_=re.compile(r'content|main|post', re.I)))
            raw_content = main_content.get_text(separator='\n', strip=True) if main_content else soup.get_text(separator='\n', strip=True)
            _save_raw_text(raw_content, url, save_dir)
            return raw_content, save_dir
        except Exception as e:
            print(f"[ERROR] 内容提取失败: URL: {url}\n错误类型: {type(e).__name__}\n详细信息: {str(e)}\n建议操作: {'请添加Cookie' if 'login' in str(e) else '检查反爬机制或重试'}")
            return None 