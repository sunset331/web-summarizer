from base import BaseSummarizer
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time
import random
from datetime import datetime
from urllib.parse import urljoin
import requests
from useragents import USER_AGENTS
from util._save_raw_text import _save_raw_text, safe_filename
from PIL import Image
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager

class ZhihuSessionManager:
    def manual_login(self) -> None:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        print("[ZhihuSessionManager] 正在打开知乎登录页面...")
        edge_options = Options()
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_zhihu")
        edge_options.add_argument(f"--user-data-dir={browser_profile_dir}")
        print(f"[INFO] 使用浏览器用户数据目录: {browser_profile_dir}")
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("https://www.zhihu.com/signin")
        print("[ZhihuSessionManager] 请在浏览器中完成登录操作...")
        input("登录完成后请按回车继续...")
        driver.quit()

    def check_login_record(self) -> bool:
        """检测user-data-dir目录下是否有Cookies文件，判断是否有登录记录"""
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_zhihu")
        cookie_path = os.path.join(browser_profile_dir, "Default", "Cookies")
        if os.path.exists(cookie_path):
            print("[ZhihuSessionManager] 检测到已有登录记录，将尝试自动复用。")
            return True
        else:
            print("[ZhihuSessionManager] 未检测到登录记录，可能需要手动登录。")
            return False

class ZhihuSummarizer(BaseSummarizer):
    def __init__(self):
        super().__init__()
        self.session_manager = ZhihuSessionManager()
        self.driver = None
        # 初始化时检测登录记录
        self.session_manager.check_login_record()

    def _init_edge_driver(self):
        """初始化Edge浏览器驱动，继承基类配置并添加知乎特有设置"""
        # 获取知乎特有的配置
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_zhihu")
        
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
        
        # 再次检测登录记录
        self.session_manager.check_login_record()

    def _close_zhihu_popup(self):
        assert self.driver is not None
        max_attempts = 3
        for _ in range(max_attempts):
            try:
                close_buttons = self.driver.find_elements(
                    By.XPATH,
                    '//button[contains(@class, "Modal-closeButton")]//*[name()="svg"][contains(@class, "Modal-closeIcon")]'
                )
                if close_buttons:
                    self.driver.execute_script("arguments[0].closest('button').click()", close_buttons[0])
                    time.sleep(1)
                    if not self.driver.find_elements(By.CLASS_NAME, "Modal-wrapper"):
                        break
            except Exception as e:
                print(f"[ERROR] 关闭弹窗时出错: {str(e)}")
                break

    def fetch_web_content(self, url: str):
        if self.driver is None:
            self._init_edge_driver()
        assert self.driver is not None
        
        self.driver.get(url)
        time.sleep(2)
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        if "/question/" in url:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//h1[contains(@class, "QuestionHeader-title")]'))
            )
            self._close_zhihu_popup()
            title = self.driver.find_element(By.XPATH, '//h1[contains(@class,"QuestionHeader-title")]').text.strip()
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            folder_name = safe_filename(f"zhihu_{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            save_dir = os.path.join(desktop, folder_name)
            img_dir = os.path.join(save_dir, "images")
            os.makedirs(img_dir, exist_ok=True)
            try:
                description_elem = self.driver.find_element(
                    By.XPATH, '//div[contains(@class,"QuestionRichText")]//span[@itemprop="text"]'
                )
                description = description_elem.text.strip()
            except Exception:
                try:
                    description_elem = self.driver.find_element(
                        By.XPATH, '//div[contains(@class,"QuestionRichText")]'
                    )
                    description = description_elem.text.strip()
                except Exception:
                    description = "无问题描述"
            seen_texts = set()
            extracted_content = []
            img_records = []
            img_index = 1
            seen_images = set()
            inserted_images = set()
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_step = 800
            current_position = 0
            while current_position < last_height:
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(random.uniform(1.0, 2.0))
                for _ in range(3):
                    expand_buttons = self.driver.find_elements(
                        By.XPATH, '//button[contains(text(), "展开阅读全文") or contains(@class, "ContentItem-expandButton")]'
                    )
                    if not expand_buttons:
                        break
                    for btn in expand_buttons:
                        try:
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(0.3)
                        except Exception:
                            continue
                    time.sleep(1)
                try:
                    content_div = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((
                            By.XPATH,
                            '//div[contains(@class,"QuestionAnswers-answers") or contains(@class,"Question-main")]'
                        ))
                    )
                except Exception as e:
                    print(f"[ERROR] 无法找到问题回答区域: {e}")
                    break
                
                try:
                    answer_divs = content_div.find_elements(By.XPATH, './/div[contains(@class, "AnswerItem") or contains(@class, "ContentItem")]')
                except Exception as e:
                    print(f"[ERROR] 获取回答元素失败: {e}")
                    current_position += scroll_step
                    continue
                
                for answer_div in answer_divs:
                    try:
                        rich_inners = answer_div.find_elements(By.CSS_SELECTOR, 'div.RichContent-inner')
                        for rich_inner in rich_inners:
                            try:
                                rich_texts = rich_inner.find_elements(By.CSS_SELECTOR, 'span.RichText')
                                for rich_text in rich_texts:
                                    try:
                                        paragraphs = rich_text.find_elements(By.TAG_NAME, 'p')
                                        answer_text = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                                        if answer_text and answer_text not in seen_texts:
                                            seen_texts.add(answer_text)
                                            extracted_content.append(answer_text)
                                        
                                        try:
                                            img_elements = rich_text.find_elements(By.XPATH, './/img')
                                        except Exception:
                                            continue
                                        
                                        for img in img_elements:
                                            try:
                                                img_url = (img.get_attribute("src") or 
                                                           img.get_attribute("data-src") or 
                                                           img.get_attribute("data-original") or
                                                           img.get_attribute("data-actualsrc"))
                                                if img_url and not img_url.startswith(("http://", "https://")):
                                                    img_url = urljoin(url, img_url)
                                                if img_url and img_url.startswith(("http://", "https://")):
                                                    if img_url in seen_images:
                                                        continue
                                                    seen_images.add(img_url)
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
                                                        except Exception:
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
                                            except Exception:
                                                continue
                                    except Exception:
                                        continue
                            except Exception:
                                continue
                    except Exception:
                        continue
                current_position += scroll_step
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > last_height:
                    last_height = new_height
            final_content = []
            for item in extracted_content:
                if isinstance(item, str) and item.startswith("[IMAGE_PLACEHOLDER:"):
                    try:
                        img_id = int(item.split(":")[1].rstrip("]"))
                        img_info = img_records[img_id]
                        path = img_info['path'].replace("\\", "/")
                        final_content.append(f"![{img_info['alt']}]({path})")
                    except Exception:
                        continue
                else:
                    final_content.append(item)
            content = "\n".join([str(item) for item in final_content])
            extracted_content = f"""# {title}\n\n## 问题描述\n{description}\n\n## 回答\n{content}"""
            _save_raw_text(extracted_content, url, save_dir)
            return extracted_content, save_dir
        else:
            print("[INFO] 进入知乎专栏页面分支")
            
            # 等待页面加载
            time.sleep(3)
            
            # 尝试多种标题选择器
            title_selectors = [
                '//h1[contains(@class,"Post-Title")]',
                '//h1[contains(@class,"PostHeader-title")]',
                '//h1[contains(@class,"title")]',
                '//div[contains(@class,"PostHeader")]//h1',
                '//article//h1',
                '//main//h1',
                '//h1',
                '//div[contains(@class,"PostHeader")]//div[contains(@class,"title")]'
            ]
            
            title = None
            for selector in title_selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    title_element = self.driver.find_element(By.XPATH, selector)
                    title = title_element.text.strip()
                    if title:
                        print(f"[INFO] 找到标题: {title}")
                        break
                except Exception as e:
                    print(f"[ERROR] 选择器 {selector} 失败: {e}")
                    continue
            
            if not title:
                # 如果都找不到，尝试获取页面标题
                title = self.driver.title.replace(" - 知乎", "").replace(" | 知乎", "")
                print(f"[INFO] 使用页面标题: {title}")
            
            if not title:
                print("[ERROR] 无法获取标题，使用默认标题")
                title = "知乎专栏文章"
            
            try:
                self._close_zhihu_popup()
            except Exception as e:
                print(f"[ERROR] 关闭弹窗失败: {e}")

            # 2. 作者信息提取（多重定位策略）
            author_info = {}
            try:
                # 尝试多种定位方式
                author_elements = [
                    '//div[contains(@class,"AuthorInfo")]//meta[@itemprop="name"]',  # meta方式
                    '//div[contains(@class,"AuthorInfo-name")]//a',  # 直接链接方式
                    '//div[contains(@class,"AuthorInfo")]//span[contains(@class,"UserLink")]'  # 备用方式
                ]
        
                for xpath in author_elements:
                    try:
                        element = self.driver.find_element(By.XPATH, xpath)
                        author_name = element.get_attribute('content') or element.text
                        if author_name:
                            author_info['name'] = author_name
                            break
                    except:
                        continue

                # 作者简介提取
                bio_elements = [
                    '//div[contains(@class,"AuthorInfo-badgeText")]',
                    '//div[contains(@class,"AuthorInfo-head")]//span[contains(@class,"RichText")]'
                ]
        
                for xpath in bio_elements:
                    try:
                        bio_text = self.driver.find_element(By.XPATH, xpath).text
                        if bio_text:
                            author_info['bio'] = bio_text
                            break
                    except:
                        continue

            except Exception as auth_error:
                print(f"[ERROR] 作者信息提取失败: {str(auth_error)}")
                author_info = {'name': '未知', 'bio': '未获取到简介'}
            
            # 确保作者信息有默认值
            if 'name' not in author_info or not author_info['name']:
                author_info['name'] = '未知作者'
            if 'bio' not in author_info or not author_info['bio']:
                author_info['bio'] = '未获取到简介'

            # 2. 创建保存目录
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            folder_name = safe_filename(f"zhihu_{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            save_dir = os.path.join(desktop, folder_name)
            img_dir = os.path.join(save_dir, "images")
            os.makedirs(img_dir, exist_ok=True)

            # 3. 滚动加载所有内容
            seen_texts = set()
            seen_images = set()
            inserted_images = set()
            extracted_content = []
            img_records = []  # 新增：用于存储图片记录
            img_index = 1
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_step = 500
            current_position = 0
            max_scroll_attempts = 20  # 最大滚动次数
            scroll_attempts = 0
            no_new_content_count = 0  # 连续无新内容的次数

            while current_position < last_height and scroll_attempts < max_scroll_attempts:
                scroll_attempts += 1
                print(f"[INFO] 第 {scroll_attempts} 次滚动，位置: {current_position}")
                
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(random.uniform(1.5, 2.5))

                # 获取正文容器
                content_selectors = [
                    '//div[contains(@class,"RichText") and contains(@class,"ztext") and contains(@class,"Post-RichText")]',
                    '//div[contains(@class,"RichText") and contains(@class,"ztext")]',
                    '//div[contains(@class,"Post-RichText")]',
                    '//div[contains(@class,"RichText")]',
                    '//article//div[contains(@class,"RichText")]',
                    '//main//div[contains(@class,"RichText")]',
                    '//div[contains(@class,"content")]',
                    '//article//div[contains(@class,"content")]',
                    '//div[contains(@class,"ztext")]'
                ]
                
                content_div = None
                for selector in content_selectors:
                    try:
                        content_div = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if content_div:
                            print(f"[INFO] 找到内容区域: {selector}")
                            break
                    except Exception as e:
                        print(f"[ERROR] 内容选择器 {selector} 失败: {e}")
                        continue
                
                if not content_div:
                    print("[INFO] 无法找到内容区域，尝试使用备用方法")
                    # 备用方法：查找包含文本内容的主要区域
                    try:
                        content_div = self.driver.find_element(By.TAG_NAME, "body")
                    except Exception as e:
                        print(f"[ERROR] 备用方法也失败: {e}")
                        current_position += scroll_step
                        continue
                
                try:
                    all_elements = content_div.find_elements(By.XPATH, "./*")
                except Exception as e:
                    print(f"[ERROR] 获取子元素失败: {e}")
                    current_position += scroll_step
                    continue
                
                print(f"[INFO] 找到 {len(all_elements)} 个子元素")
                processed_count = 0
                
                # 按顺序遍历所有元素，保持原文顺序
                for element in all_elements:
                    try:
                        tag_name = element.tag_name.lower()
                        text = (element.get_attribute('textContent') or '').strip()
                        img_elements = []
                        
                        # 首先检查是否是代码高亮容器
                        if tag_name == 'div':
                            cls = element.get_attribute("class") or ""
                            if "highlight" in cls:
                                print(f"[INFO] 发现highlight容器: {cls}")
                                # 查找内部的pre和code元素
                                pre_elements = element.find_elements(By.XPATH, ".//pre")
                                print(f"[INFO] 找到 {len(pre_elements)} 个pre元素")
                                for pre_elem in pre_elements:
                                    try:
                                        code_elem = pre_elem.find_element(By.XPATH, ".//code")
                                        code_text = (code_elem.get_attribute('textContent') or '').strip()
                                        print(f"[INFO] 从highlight提取代码，长度: {len(code_text)}")
                                        if code_text and code_text not in seen_texts:
                                            seen_texts.add(code_text)
                                            # 检测语言类型
                                            lang = ""
                                            try:
                                                code_class = code_elem.get_attribute("class") or ""
                                                if "language-" in code_class:
                                                    lang = code_class.split("language-")[1].split()[0]
                                                elif "lang-" in code_class:
                                                    lang = code_class.split("lang-")[1].split()[0]
                                            except:
                                                pass
                                            
                                            if lang:
                                                extracted_content.append(f"\n```{lang}\n{code_text}\n```\n")
                                            else:
                                                extracted_content.append(f"\n```\n{code_text}\n```\n")
                                            processed_count += 1
                                            print(f"[INFO] 从highlight容器提取代码块，语言: {lang}，长度: {len(code_text)}")
                                    except Exception as e:
                                        print(f"[ERROR] 处理highlight中的pre元素失败: {e}")
                                        continue
                            else:
                                # 处理普通的div文本
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    extracted_content.append(text)
                                    processed_count += 1
                        elif tag_name in ["figure"]:
                            try:
                                img_elements = element.find_elements(By.XPATH, ".//img")
                            except Exception:
                                continue
                            for img in img_elements:
                                try:
                                    img_url = (img.get_attribute("src") or 
                                            img.get_attribute("data-src") or 
                                            img.get_attribute("data-original") or
                                            img.get_attribute("data-actualsrc"))
                                    if img_url and not img_url.startswith(("http://", "https://")):
                                        img_url = urljoin(url, img_url)
                                    if img_url and img_url.startswith(("http://", "https://")):
                                        if img_url in seen_images:
                                            continue
                                        seen_images.add(img_url)
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
                                            except Exception:
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
                                            print(f"[INFO] 提取图片: {alt_text}")
                                except Exception:
                                    continue
                        elif tag_name in ['ul', 'ol']:
                            try:
                                list_items = []
                                for li in element.find_elements(By.XPATH, "./li"):
                                    li_text = (li.get_attribute('textContent') or '').strip()
                                    if li_text and li_text not in seen_texts:
                                        seen_texts.add(li_text)
                                        list_items.append(f"• {li_text}")
                                if list_items:
                                    extracted_content.append("\n".join(list_items))
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name == 'pre':
                            try:
                                # 处理代码块
                                code_element = element.find_element(By.XPATH, ".//code")
                                if code_element:
                                    code_text = (code_element.get_attribute('textContent') or '').strip()
                                    if code_text and code_text not in seen_texts:
                                        seen_texts.add(code_text)
                                        # 检测语言类型
                                        lang = ""
                                        try:
                                            code_class = code_element.get_attribute("class") or ""
                                            if "language-" in code_class:
                                                lang = code_class.split("language-")[1].split()[0]
                                            elif "lang-" in code_class:
                                                lang = code_class.split("lang-")[1].split()[0]
                                        except:
                                            pass
                                        
                                        if lang:
                                            extracted_content.append(f"\n```{lang}\n{code_text}\n```\n")
                                        else:
                                            extracted_content.append(f"\n```\n{code_text}\n```\n")
                                        processed_count += 1
                                        print(f"[INFO] 提取代码块，语言: {lang}，长度: {len(code_text)}")
                                else:
                                    code_text = (element.get_attribute('textContent') or '').strip()
                                    if code_text and code_text not in seen_texts:
                                        seen_texts.add(code_text)
                                        extracted_content.append(f"\n```\n{code_text}\n```\n")
                                        processed_count += 1
                                        print(f"[INFO] 提取代码块，长度: {len(code_text)}")
                            except Exception:
                                continue
                        elif tag_name == 'code':
                            try:
                                # 处理行内代码
                                code_text = (element.get_attribute('textContent') or '').strip()
                                if code_text and code_text not in seen_texts:
                                    seen_texts.add(code_text)
                                    extracted_content.append(f"`{code_text}`")
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            try:
                                level = int(tag_name[1])
                                if text not in seen_texts:
                                    seen_texts.add(text)
                                    extracted_content.append(f"\n{'#' * level} {text}\n")
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name in ['p', 'span']:
                            try:
                                cls = element.get_attribute("class") or ""
                                if "RichContent-EntityWord" in cls:
                                    text = text.replace("⍟", "").strip()
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    if "bold" in cls.lower() or "strong" in cls.lower():
                                        extracted_content.append(f"**{text}**")
                                    else:
                                        extracted_content.append(text)
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name == 'blockquote':
                            try:
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    extracted_content.append(f"> {text}")
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name == 'strong' or tag_name == 'b':
                            try:
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    extracted_content.append(f"**{text}**")
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name == 'em' or tag_name == 'i':
                            try:
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    extracted_content.append(f"*{text}*")
                                    processed_count += 1
                            except Exception:
                                continue
                        elif tag_name == 'a':
                            try:
                                href = element.get_attribute("href") or ""
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    if href and href.startswith(("http://", "https://")):
                                        extracted_content.append(f"[{text}]({href})")
                                    else:
                                        extracted_content.append(text)
                                    processed_count += 1
                            except Exception:
                                continue
                    except Exception as e:
                        # 如果单个元素处理失败，继续处理下一个元素
                        continue
                
                print(f"[INFO] 本次滚动处理了 {processed_count} 个元素")
                print(f"[INFO] 当前已提取内容数量: {len(extracted_content)}")
                
                # 检查是否有新内容
                if processed_count == 0:
                    no_new_content_count += 1
                    print(f"[INFO] 连续 {no_new_content_count} 次没有新内容")
                    if no_new_content_count >= 3:  # 连续3次没有新内容就停止
                        print("[INFO] 连续多次没有新内容，停止滚动")
                        break
                else:
                    no_new_content_count = 0  # 重置计数器
                
                # 更新滚动位置
                current_position += scroll_step
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > last_height:
                    last_height = new_height
            
            # 生成最终内容前，替换占位符
            final_content = []
            
            for item in extracted_content:
                item_str = str(item)
                if item_str.startswith("[IMAGE_PLACEHOLDER:"):
                    try:
                        img_id = int(item_str.split(":")[1].rstrip("]"))
                        img_info = img_records[img_id]
                        path = img_info['path'].replace("\\", "/")  # 处理路径分隔符
                        if not os.path.exists(img_info['path']):
                            print(f"[ERROR] 文件不存在 - {img_info['path']}")
                        final_content.append(f"![{img_info['alt']}]({path})")
                    except Exception as e:
                        print(f"[ERROR] 处理占位符失败：{item}，错误：{e}")
                else:
                    final_content.append(item_str)
            
            extracted_content = final_content
            content = "\n".join(extracted_content)
            # 提取评论区内容
            comments_content = self._extract_zhihu_column_comments()
            
            extracted_content = f"""# {title}\n\n## 作者信息\n姓名：{author_info['name']}\n简介：{author_info['bio']}\n\n## 正文内容\n{content}\n"""
            
            # 如果有评论，添加到内容中
            if comments_content:
                extracted_content += f"\n## 评论区\n{comments_content}\n"
            
            _save_raw_text(extracted_content, url, save_dir)
            return extracted_content, save_dir

    def _extract_zhihu_column_comments(self) -> str:
        """知乎专栏评论区：顺序分组主评论和回复，输出树状结构"""
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
                '//div[@data-za-detail-view-path-module="CommentList"]',
                '//div[contains(@class, "Comments-container")]',
                '//div[contains(@class, "CommentList")]'
            ]
            for selector in comment_selectors:
                try:
                    comment_container = self.driver.find_element(By.XPATH, selector)
                    if comment_container:
                        print("[INFO] 找到评论区容器")
                        break
                except Exception:
                    continue
            if not comment_container:
                print("[ERROR] 未找到评论区容器")
                return ""
            # 获取评论数量
            comment_count = "未知"
            try:
                count_element = comment_container.find_element(By.XPATH, './/div[contains(@class, "css-1k10w8f")]')
                comment_count = count_element.text.strip()
                print(f"[INFO] 评论数量: {comment_count}")
            except Exception:
                print("[ERROR] 无法获取评论数量")
            # 找到评论区主容器（如.css-18ld3w0）
            try:
                main_comment_area = comment_container.find_element(By.CSS_SELECTOR, '.css-18ld3w0')
            except Exception:
                print("[ERROR] 未找到主评论区容器 .css-18ld3w0")
                return ""
            # 递归树状分组主评论和回复
            def parse_comment(div, level=0):
                try:
                    username = div.find_element(By.XPATH, './/a[contains(@class, "css-10u695f")]').text.strip()
                except Exception:
                    username = "未知用户"
                try:
                    comment_text = div.find_element(By.XPATH, './/div[contains(@class, "CommentContent")]').text.strip()
                except Exception:
                    comment_text = ""
                try:
                    comment_time = div.find_element(By.XPATH, './/span[contains(@class, "css-12cl38p")]').text.strip()
                except Exception:
                    comment_time = ""
                try:
                    like_button = div.find_element(By.XPATH, './/button[contains(@class, "Button--withLabel")]')
                    like_text = like_button.text.strip()
                    like_count = like_text if like_text and like_text not in ["回复", "喜欢"] else ""
                except Exception:
                    like_count = ""
                is_author = False
                try:
                    author_badge = div.find_element(By.XPATH, './/span[contains(@class, "css-8v0dsd") and text()="作者"]')
                    is_author = True
                except Exception:
                    pass
                # 递归查找直接子评论
                child_divs = div.find_elements(By.XPATH, './div[@data-id]')
                replies = [parse_comment(child, level+1) for child in child_divs]
                return {
                    'username': username,
                    'content': comment_text,
                    'time': comment_time,
                    'like_count': like_count,
                    'is_author': is_author,
                    'replies': replies,
                    'level': level
                }
            # 只查找一级主评论（父级是main_comment_area的直接div[data-id]）
            main_comments = []
            for div in main_comment_area.find_elements(By.XPATH, './div[@data-id]'):
                main_comments.append(parse_comment(div, 0))
            # 格式化输出
            def format_comments(comments):
                lines = []
                for idx, comment in enumerate(comments, 1):
                    indent = '  ' * comment['level']
                    if comment['level'] == 0:
                        lines.append(f"{indent}### 评论 {idx}")
                    else:
                        lines.append(f"{indent}#### 回复")
                    userline = f"{indent}**用户**: {comment['username']}"
                    if comment['is_author']:
                        userline += " (作者)"
                    lines.append(userline)
                    lines.append(f"{indent}**时间**: {comment['time']}")
                    if comment['like_count']:
                        lines.append(f"{indent}**点赞**: {comment['like_count']}")
                    lines.append(f"{indent}**内容**: {comment['content']}")
                    # 递归输出回复
                    if comment['replies']:
                        lines.extend(format_comments(comment['replies']))
                return lines
            if main_comments:
                comments_text = f"**评论总数**: {comment_count}\n\n" + "\n".join(format_comments(main_comments))
                print(f"[INFO] 成功递归树状分组主评论和回复")
                return comments_text
            else:
                print("[ERROR] 没有提取到评论")
                return ""
        except Exception as e:
            print(f"[ERROR] 评论区分组提取过程中出错: {e}")
            return ""