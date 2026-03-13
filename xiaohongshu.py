from base import BaseSummarizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import os
import time
from datetime import datetime
from urllib.parse import urljoin
import requests
import random
from useragents import USER_AGENTS
from util._save_raw_text import _save_raw_text, safe_filename
from PIL import Image

class XiaohongshuSessionManager:
    """小红书专用的会话管理器"""
    
    def __init__(self):
        pass

    def manual_login(self) -> None:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        print("[XiaohongshuSessionManager] 正在打开小红书登录页面...")
        edge_options = Options()
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_xiaohongshu")
        edge_options.add_argument(f"--user-data-dir={browser_profile_dir}")
        print(f"[INFO] 使用浏览器用户数据目录: {browser_profile_dir}")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("https://www.xiaohongshu.com/login")
        print("[XiaohongshuSessionManager] 请在浏览器中完成登录操作...")
        input("登录完成后请按回车继续...")
        driver.quit()

class XiaohongshuSummarizer(BaseSummarizer):
    def __init__(self):
        super().__init__()
        self.session_manager = XiaohongshuSessionManager()
        self.driver = None

    def _init_edge_driver(self):
        """初始化Edge浏览器驱动，继承基类配置并添加小红书特有设置"""
        # 获取小红书特有的配置
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_xiaohongshu")
        
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

    def _close_xiaohongshu_popup(self):
        assert self.driver is not None
        max_attempts = 3
        for _ in range(max_attempts):
            try:
                close_buttons = self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "close") and contains(@class, "icon-btn-wrapper")]'
                )
                if close_buttons:
                    self.driver.execute_script("arguments[0].click()", close_buttons[0])
                    time.sleep(1)
                    if not self.driver.find_elements(By.XPATH, '//div[contains(@class, "close")]'):
                        break
            except Exception as e:
                print(f"[ERROR] 关闭小红书弹窗时出错: {str(e)}")
                break

    def fetch_web_content(self, url: str):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.driver is None:
                    self._init_edge_driver()
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                if "xhslink.com" in url:
                    try:
                        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                        url = resp.url
                    except Exception as e:
                        print(f"[ERROR] 小红书短链跳转失败: {e}")
                        return None
                assert self.driver is not None
                self.driver.get(url)
                time.sleep(3)  # 增加等待时间
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@id="detail-title"]'))
                )
                self._close_xiaohongshu_popup()
                title = self.driver.find_element(By.XPATH, '//div[@id="detail-title"]').text.strip()
                author = self.driver.find_element(By.XPATH, '//span[@class="username"]').text.strip()
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                folder_name = safe_filename(f"xiaohongshu_{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                save_dir = os.path.join(desktop, folder_name)
                img_dir = os.path.join(save_dir, "images")
                os.makedirs(img_dir, exist_ok=True)
                desc_element = self.driver.find_element(By.XPATH, '//div[@id="detail-desc"]')
                content_text = desc_element.text.strip()
                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                main_imgs = self.driver.find_elements(By.XPATH, '//img[contains(@class,"note-slider-img")]')
                desc_imgs = desc_element.find_elements(By.XPATH, './/img')
                all_imgs = main_imgs + desc_imgs
                img_url_set = set()
                img_records = []
                img_index = 1
                inserted_images = set()
                extracted_content: list[str] = [content_text]
                for img in all_imgs:  # type: ignore
                    try:
                        img_url = (img.get_attribute("src") or 
                                img.get_attribute("data-src") or 
                                img.get_attribute("data-original") or
                                img.get_attribute("data-actualsrc"))
                        if img_url and not img_url.startswith(("http://", "https://")):
                            img_url = urljoin(url, img_url)
                        if img_url and img_url.startswith(("http://", "https://")):
                            if img_url in img_url_set:
                                continue
                            img_url_set.add(img_url)
                            img_name = safe_filename(f"image_{img_index}.jpg")
                            abs_img_path = os.path.join(img_dir, img_name)
                            if not os.path.exists(abs_img_path):
                                try:
                                    img_data = requests.get(img_url, headers=headers, timeout=10).content
                                    # 先保存原始图片到临时文件
                                    tmp_path = abs_img_path + ".tmp"
                                    with open(tmp_path, 'wb') as f:
                                        f.write(img_data)
                                    # 用Pillow转换为jpg
                                    try:
                                        with Image.open(tmp_path) as img_pil:
                                            rgb_img = img_pil.convert('RGB')
                                            rgb_img.save(abs_img_path, format='JPEG')
                                        os.remove(tmp_path)
                                    except Exception as e:
                                        print(f"[ERROR] 图片格式转换失败: {e}")
                                        os.rename(tmp_path, abs_img_path)  # 保底直接重命名
                                except Exception as download_error:
                                    print(f"[ERROR] 图片下载失败: {str(download_error)}")
                                    continue
                            # 只有下载和保存成功后，才获取alt_text
                            alt_text = img.get_attribute("alt") or "图片"
                            if img_url not in inserted_images:
                                img_records.append({
                                    'path': os.path.join(img_dir, img_name),
                                    'alt': alt_text
                                })
                                extracted_content.append(f"[IMAGE_PLACEHOLDER:{len(img_records)-1}]")
                                img_index += 1
                                inserted_images.add(img_url)
                    except Exception as e:
                        print(f"[ERROR] 图片处理失败: {str(e)}")
                        continue
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
                # 提取评论区内容
                comments_content = self._extract_comments()
                
                extracted_content_str = f"""# {title}\n\n## 作者信息\n用户名：{author}\n\n## 正文内容\n{chr(10).join(final_content)}\n"""
                
                # 如果有评论，添加到内容中
                if comments_content:
                    extracted_content_str += f"\n## 评论区\n{comments_content}\n"
                
                _save_raw_text(extracted_content_str, url, save_dir)
                # 收集图片路径列表，供多模态API使用
                img_paths = [img_info['path'] for img_info in img_records]
                return extracted_content_str, save_dir, img_paths
                
            except Exception as e:
                print(f"[ERROR] 尝试 {attempt + 1}/{max_retries} 处理失败: {str(e)}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                if attempt < max_retries - 1:
                    print("[INFO] 等待5秒后重试...")
                    time.sleep(5)
                else:
                    print("[ERROR] 所有重试都失败")
                    return None

    def _extract_comments(self) -> str:
        """提取小红书评论区的评论内容，支持主评论和递归回复结构"""
        try:
            if self.driver is None:
                print("[ERROR] driver为None，无法提取评论")
                return ""
            
            # 滚动到评论区
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 查找评论区容器
            comment_container = None
            comment_selectors = [
                '//div[contains(@class, "comment")]',
                '//div[contains(@class, "CommentList")]',
                '//div[contains(@class, "comments")]',
                '//div[contains(@class, "comment-list")]',
                '//div[contains(@class, "comment-container")]'
            ]
            for selector in comment_selectors:
                try:
                    comment_container = self.driver.find_element(By.XPATH, selector)
                    if comment_container:
                        print("[INFO] 找到小红书评论区容器")
                        break
                except Exception:
                    continue
            if not comment_container:
                print("[ERROR] 未找到小红书评论区容器")
                return ""
            
            # 主评论：parent-comment下的comment-item（不含comment-item-sub）
            main_comment_items = comment_container.find_elements(
                By.XPATH, './/div[contains(@class, "parent-comment")]/div[contains(@class, "comment-item") and not(contains(@class, "comment-item-sub"))]'
            )
            print(f"[INFO] 找到 {len(main_comment_items)} 条主评论")
            
            def parse_comment_item(comment_element, level=0):
                # 用户名
                username = "未知用户"
                try:
                    username_element = comment_element.find_element(By.XPATH, './/a[contains(@class, "name")]')
                    username = username_element.text.strip()
                except Exception:
                    pass
                # 内容
                comment_text = ""
                try:
                    content_element = comment_element.find_element(By.XPATH, './/div[contains(@class, "content")]//span[contains(@class, "note-text")]')
                    comment_text = content_element.text.strip()
                except Exception:
                    try:
                        content_element = comment_element.find_element(By.XPATH, './/div[contains(@class, "content")]')
                        comment_text = content_element.text.strip()
                    except Exception:
                        pass
                # 时间
                comment_time = ""
                try:
                    time_element = comment_element.find_element(By.XPATH, './/div[contains(@class, "date")]/span[1]')
                    comment_time = time_element.text.strip()
                except Exception:
                    pass
                # 只在当前主评论下查找直接下级的reply-container
                replies = []
                try:
                    reply_container = comment_element.find_element(By.XPATH, './following-sibling::div[contains(@class, "reply-container")]')
                    reply_items = reply_container.find_elements(By.XPATH, './div[contains(@class, "list-container")]/div[contains(@class, "comment-item-sub")]')
                    for reply_item in reply_items:
                        reply_data = parse_comment_item(reply_item, level + 1)
                        if reply_data and reply_data['content']:
                            replies.append(reply_data)
                except Exception:
                    pass
                return {
                    'username': username,
                    'content': comment_text,
                    'time': comment_time,
                    'replies': replies,
                    'level': level
                }
            
            main_comments = []
            comment_index = 1
            for comment_item in main_comment_items:
                comment_data = parse_comment_item(comment_item, 0)
                if comment_data and comment_data['content']:
                    comment_data['index'] = comment_index
                    main_comments.append(comment_data)
                    comment_index += 1
            
            def format_comment(comment, level=0):
                lines = []
                indent = '  ' * level
                if level == 0:
                    lines.append(f"{indent}### 评论 {comment['index']}")
                else:
                    lines.append(f"{indent}#### 回复")
                lines.append(f"{indent}**用户**: {comment['username']}")
                if comment['time']:
                    lines.append(f"{indent}**时间**: {comment['time']}")
                lines.append(f"{indent}**内容**: {comment['content']}")
                for reply in comment['replies']:
                    lines.extend(format_comment(reply, level + 1))
                return lines
            
            if main_comments:
                all_lines = []
                for comment in main_comments:
                    all_lines.extend(format_comment(comment))
                comments_text = f"**评论总数**: {len(main_comments)} 条\n\n" + "\n".join(all_lines)
                print(f"[INFO] 成功提取 {len(main_comments)} 条主评论及其回复")
                return comments_text
            else:
                print("[ERROR] 没有提取到小红书评论")
                return ""
        except Exception as e:
            print(f"[ERROR] 小红书评论区提取过程中出错: {e}")
            return "" 