from base import BaseSummarizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from util.edge_driver_manager import ensure_edge_driver
from util.xhs_session_maintenance import maybe_clear_expired_xhs_session
import os
import time
from datetime import datetime
from urllib.parse import urljoin
import requests
import random
from useragents import USER_AGENTS
from util._save_raw_text import _save_raw_text, safe_filename
from PIL import Image
import re
import threading
from typing import Optional

# 避免多线程同时用同一 user-data-dir 启多个 Edge，导致 “Chrome instance exited” / 配置目录锁
_xhs_fetch_lock = threading.Lock()


def _is_note_cdn_url(u: str) -> bool:
    """笔记配图 CDN（排除头像等）；正文图 URL 均含 notes_pre_post。"""
    if not u or "xhscdn.com" not in u:
        return False
    if "sns-avatar" in u:
        return False
    return "notes_pre_post" in u

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
        """初始化Edge浏览器驱动，继承基类配置并添加小红书特有设置。驱动由 edge_driver_manager 检测/更新。"""
        browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_xiaohongshu")
        # 须在启动 Edge 前执行：删除 Cookie 库文件；不得与已占用该 user-data-dir 的进程并发
        maybe_clear_expired_xhs_session(browser_profile_dir)
        edge_options = self._get_base_edge_options()
        edge_options.add_argument(f"--user-data-dir={browser_profile_dir}")
        # 无显示器会话 / 远程桌面断开后可设 WEB_SUMMARIZER_EDGE_HEADLESS=1
        _hl = os.environ.get("WEB_SUMMARIZER_EDGE_HEADLESS", "").strip().lower()
        if _hl in ("1", "true", "yes"):
            edge_options.add_argument("--headless=new")
        try:
            driver_path = ensure_edge_driver()
            self.driver = webdriver.Edge(service=Service(driver_path), options=edge_options)
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
            )
            self.driver.set_window_size(1920, 1080)
        except Exception as e:
            print(f"[ERROR] Edge浏览器初始化失败: {e}")
            if "Could not reach host" in str(e) or "getaddrinfo failed" in str(e):
                print("[ERROR] 网络连接失败，无法自动下载Edge驱动")
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

    def _scroll_note_media_into_view(self) -> None:
        assert self.driver is not None
        self.driver.execute_script(
            """
            var el = document.querySelector('.media-container') || document.querySelector('.note-slider');
            if (el) { el.scrollIntoView({block:'center', behavior:'instant'}); }
            """
        )

    def _collect_note_image_urls_ordered(self) -> list[str]:
        """小红书轮播图常为懒加载，img.src 可能为空，需读 currentSrc；并兜底解析页面 HTML。"""
        assert self.driver is not None
        merged: list[str] = []
        seen: set[str] = set()

        def push(u: str) -> None:
            if not u or not u.startswith(("http://", "https://")):
                return
            if not _is_note_cdn_url(u):
                return
            if u in seen:
                return
            seen.add(u)
            merged.append(u)

        js_urls = self.driver.execute_script(
            """
            const seen = new Set();
            const out = [];
            function push(u) {
              if (!u || !u.startsWith('http')) return;
              if (u.includes('sns-avatar')) return;
              if (u.includes('/avatar/1040g')) return;
              if (!u.includes('notes_pre_post')) return;
              if (seen.has(u)) return;
              seen.add(u); out.push(u);
            }
            for (const im of document.querySelectorAll('img')) {
              push(im.getAttribute('src') || '');
              push(im.currentSrc || '');
              push(im.getAttribute('data-src') || '');
            }
            return out;
            """
        )
        if isinstance(js_urls, list):
            for u in js_urls:
                if isinstance(u, str):
                    push(u)

        html = self.driver.page_source or ""
        for m in re.finditer(
            r'https://sns-webpic[^"\'\s<>]+?/notes_pre_post/[^"\'\s<>]+',
            html,
            flags=re.I,
        ):
            push(m.group(0))

        return merged

    def fetch_web_content(self, url: str, work_dir: Optional[str] = None):
        with _xhs_fetch_lock:
            return self._fetch_web_content_impl(url, work_dir)

    def _fetch_web_content_impl(self, url: str, work_dir: Optional[str] = None):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.driver is None:
                    self._init_edge_driver()
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    # 小红书图床常校验 Referer，否则可能 403 或空内容
                    'Referer': 'https://www.xiaohongshu.com/',
                }
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
                try:
                    author = self.driver.find_element(By.XPATH, '//span[@class="username"]').text.strip()
                except Exception:
                    author = self.driver.find_element(
                        By.XPATH, '//a[contains(@class,"name")]//span[contains(@class,"username")]'
                    ).text.strip()
                if work_dir:
                    save_dir = os.path.abspath(work_dir)
                    os.makedirs(save_dir, exist_ok=True)
                else:
                    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                    folder_name = safe_filename(
                        f"xiaohongshu_{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    )
                    save_dir = os.path.join(desktop, folder_name)
                img_dir = os.path.join(save_dir, "images")
                os.makedirs(img_dir, exist_ok=True)
                desc_element = self.driver.find_element(By.XPATH, '//div[@id="detail-desc"]')
                content_text = desc_element.text.strip()
                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                self._scroll_note_media_into_view()
                time.sleep(1.5)
                try:
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".media-container img, img.note-slider-img")
                        )
                    )
                except Exception:
                    print("[WARNING] 等待轮播图片节点超时，继续用 JS/HTML 解析 URL")

                primary_urls = self._collect_note_image_urls_ordered()
                print(f"[INFO] 解析到笔记图片 URL 数量: {len(primary_urls)}")
                # 优先笔记轮播区域，避免抓到侧栏头像等（见页面结构 media-container / note-slider-img）
                main_imgs = self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class,"media-container")]//img[contains(@class,"note-slider-img")]',
                )
                if not main_imgs:
                    main_imgs = self.driver.find_elements(
                        By.XPATH, '//img[contains(@class,"note-slider-img")]'
                    )
                desc_imgs = desc_element.find_elements(By.XPATH, './/img')
                all_imgs = main_imgs + desc_imgs
                if not all_imgs:
                    print("[WARNING] 未匹配到默认图片节点，尝试 CDN 图片备用 XPath...")
                    all_imgs = self.driver.find_elements(
                        By.XPATH,
                        '//img[contains(@src,"xhscdn") or contains(@src,"sns-webpic") '
                        'or contains(@src,"sns-webpic-qc") or contains(@src,"spectrum")]',
                    )
                img_url_set = set()
                img_records = []
                img_index = 1
                inserted_images = set()
                extracted_content: list[str] = [content_text]

                def _resolve_img_url_from_element(img_el) -> str:
                    u = (
                        img_el.get_attribute("src")
                        or img_el.get_attribute("data-src")
                        or img_el.get_attribute("data-original")
                        or img_el.get_attribute("data-actualsrc")
                        or ""
                    )
                    if (not u or not u.startswith(("http://", "https://"))) and self.driver is not None:
                        try:
                            u = self.driver.execute_script(
                                "var e=arguments[0]; return (e.currentSrc||e.src||e.getAttribute('data-src')||'').trim();",
                                img_el,
                            ) or ""
                        except Exception:
                            pass
                    if u and not u.startswith(("http://", "https://")):
                        u = urljoin(url, u)
                    return u

                # 优先使用 JS + 源码解析到的 URL（解决懒加载 src 为空）
                url_walk_order: list[str] = []
                if primary_urls:
                    url_walk_order = list(primary_urls)
                else:
                    for img in all_imgs:  # type: ignore
                        cand = _resolve_img_url_from_element(img)
                        if cand and _is_note_cdn_url(cand):
                            if cand not in url_walk_order:
                                url_walk_order.append(cand)
                        elif cand and cand.startswith(("http://", "https://")):
                            if "note-slider-img" in (img.get_attribute("class") or "") and cand not in url_walk_order:
                                url_walk_order.append(cand)

                for img_url in url_walk_order:
                    try:
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
                            alt_text = "图片"
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
                            rel = os.path.relpath(img_info["path"], save_dir).replace("\\", "/")
                            final_content.append(f"![{img_info['alt']}]({rel})")
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