from base import BaseSummarizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import os
import time
import re
from datetime import datetime
from urllib.parse import urljoin
from util._save_raw_text import _save_raw_text, safe_filename
from PIL import Image
import requests

class WeixinSessionManager:
    def manual_login(self) -> None:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        print("[WeixinSessionManager] 正在打开微信公众号登录页面...")
        edge_options = Options()
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_weixin")
        edge_options.add_argument(f"--user-data-dir={browser_profile_dir}")
        print(f"[DEBUG] 使用浏览器用户数据目录: {browser_profile_dir}")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("https://mp.weixin.qq.com/")
        print("[WeixinSessionManager] 请在浏览器中完成登录操作...")
        input("登录完成后请按回车继续...")
        driver.quit()

class WeixinSummarizer(BaseSummarizer):
    def __init__(self):
        super().__init__()
        self.session_manager = WeixinSessionManager()
        self.driver = None

    def _init_edge_driver(self):
        """初始化Edge浏览器驱动，继承基类配置并添加微信特有设置"""
        # 获取微信特有的配置
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_weixin")
        
        # 调用父类方法获取基础配置，并传入额外的选项
        edge_options = self._get_base_edge_options()
        edge_options.add_argument(f"--user-data-dir={browser_profile_dir}")
        
        try:
            # 首先尝试使用本地msedgedriver
            local_driver_path = self._find_local_msedgedriver()
            
            if local_driver_path:
                print(f"[INFO] 使用本地Edge驱动: {local_driver_path}")
                self.driver = webdriver.Edge(
                    service=Service(local_driver_path),
                    options=edge_options
                )
            else:
                print("[WARNING] 未找到本地Edge驱动，尝试自动下载...")
                # 如果本地没有，尝试自动下载（可能失败）
                self.driver = webdriver.Edge(
                    service=Service(EdgeChromiumDriverManager().install()),
                    options=edge_options
                )
            
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
            )
            # 设置窗口大小为桌面版
            self.driver.set_window_size(1920, 1080)
            
        except Exception as e:
            print(f"[ERROR] Edge浏览器初始化失败: {e}")
            if "Could not reach host" in str(e) or "getaddrinfo failed" in str(e):
                print("[ERROR] 网络连接失败，无法自动下载Edge驱动")
                print("[SOLUTION] 请确保已下载msedgedriver.exe并放置在以下位置之一：")
                print("  1. 项目根目录")
                print("  2. D:\\edgedriver_win64\\ (当前检测到的路径)")
                print("  3. 系统PATH中的任何目录")
                print(f"[INFO] 当前检测到的本地驱动路径: {self._find_local_msedgedriver()}")
            raise

    def fetch_web_content(self, url: str):
        if self.driver is None:
            self._init_edge_driver()
        assert self.driver is not None
        self.driver.get(url)
        time.sleep(2)
        assert self.driver is not None
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//h1[@id="activity-name"]'))
        )
        title = self.driver.find_element(By.XPATH, '//h1[@id="activity-name"]').text.strip()
        author = self.driver.find_element(By.XPATH, '//div[@id="meta_content"]').text.strip()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        folder_name = safe_filename(f"weixin_{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        save_dir = os.path.join(desktop, folder_name)
        img_dir = os.path.join(save_dir, "images")
        os.makedirs(img_dir, exist_ok=True)
        print("[INFO] 页面加载后等待5秒...")
        time.sleep(5)
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_step = 300
        current_position = 0
        while current_position < last_height:
            self.driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(0.5)
            current_position += scroll_step
            last_height = self.driver.execute_script("return document.body.scrollHeight")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        content_div = self.driver.find_element(By.XPATH, '//div[@id="js_content"]')
        img_records = []
        img_index = [1]
        inserted_images = set()
        seen_texts = set()
        
        def extract_content(element):
            content = []
            tag_name = element.tag_name.lower()
            if tag_name == 'img':
                img_url = (
                    element.get_attribute("src") or 
                    element.get_attribute("data-src") or 
                    element.get_attribute("data-original") or
                    element.get_attribute("data-actualsrc")
                )
                if img_url:
                    img_url = urljoin(url, img_url.split('?')[0])
                if img_url and img_url not in inserted_images:
                    img_name = safe_filename(f"image_{img_index[0]}.jpg")
                    abs_img_path = os.path.join(img_dir, img_name)
                    
                    # 使用requests直接下载图片
                    if not os.path.exists(abs_img_path):
                        try:
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Referer': url
                            }
                            img_response = requests.get(img_url, headers=headers, timeout=10)
                            img_response.raise_for_status()
                            
                            # 先保存原始图片到临时文件
                            tmp_path = abs_img_path + ".tmp"
                            with open(tmp_path, 'wb') as f:
                                f.write(img_response.content)
                            
                            # 用Pillow转换为jpg
                            try:
                                with Image.open(tmp_path) as img:
                                    rgb_img = img.convert('RGB')
                                    rgb_img.save(abs_img_path, format='JPEG')
                                os.remove(tmp_path)
                            except Exception as e:
                                print(f"[ERROR] 图片格式转换失败: {e}")
                                os.rename(tmp_path, abs_img_path)  # 保底直接重命名
                                
                        except Exception as download_error:
                            print(f"[ERROR] 图片下载失败: {str(download_error)}")
                            pass  # 跳过这张图片，继续处理下一张
                    
                    img_records.append({
                        'path': os.path.join(img_dir, img_name),
                        'alt': element.get_attribute("alt") or "图片"
                    })
                    content.append(f"[IMAGE_PLACEHOLDER:{len(img_records)-1}]")
                    img_index[0] += 1
                    inserted_images.add(img_url)
            else:
                children = element.find_elements(By.XPATH, './*')
                if not children:
                    text = (element.get_attribute('textContent') or '').strip()
                    norm_text = re.sub(r'\s+', '', text)
                    if norm_text and norm_text not in seen_texts:
                        content.append(text)
                        seen_texts.add(norm_text)
                for child in children:
                    content.extend(extract_content(child))
            return content
        
        extracted_content = extract_content(content_div)
        final_content = []
        for item in extracted_content:
            if isinstance(item, str) and item.startswith("[IMAGE_PLACEHOLDER:"):
                try:
                    img_id = int(item.split(":")[1].rstrip("]"))
                    img_info = img_records[img_id]
                    path = img_info['path'].replace("\\", "/")
                    final_content.append(f"![{img_info['alt']}]({path})")
                except Exception as e:
                    print(f"[ERROR] 图片占位符处理失败: {e}")
                    continue
            else:
                final_content.append(item)
        
        extracted_content = f"""# {title}\n\n## 作者信息\n{author}\n\n## 正文内容\n{chr(10).join(final_content)}\n"""
        _save_raw_text(extracted_content, url, save_dir)
        return extracted_content, save_dir 