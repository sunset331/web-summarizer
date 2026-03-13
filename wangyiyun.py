from base import BaseSummarizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import time
import os

class WangyiyunSessionManager:
    """网易云专用的会话管理器"""
    
    def __init__(self):
        self.browser_profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_wangyiyun")
        os.makedirs(self.browser_profile_dir, exist_ok=True)

    def manual_login(self) -> None:
        print("[WangyiyunSessionManager] 正在打开网易云登录页面...")
        edge_options = webdriver.EdgeOptions()
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        edge_options.add_argument(f"--user-data-dir={self.browser_profile_dir}")
        print(f"[INFO] 使用浏览器用户数据目录: {self.browser_profile_dir}")
        
        driver = webdriver.Edge(options=edge_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("https://music.163.com/")
        print("[WangyiyunSessionManager] 请在浏览器中完成登录操作...")
        
        # 自动检测登录状态，而不是手动输入回车
        max_wait_time = 300  # 最多等待5分钟
        check_interval = 3   # 每3秒检查一次
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                # 检查是否已登录
                if self._check_login_status(driver):
                    print("[WangyiyunSessionManager] 检测到登录成功！")
                    break
                else:
                    print(f"[WangyiyunSessionManager] 等待登录中... ({elapsed_time}/{max_wait_time}秒)")
                    time.sleep(check_interval)
                    elapsed_time += check_interval
            except Exception as e:
                print(f"[WangyiyunSessionManager] 检查登录状态时出错: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        if elapsed_time >= max_wait_time:
            print("[WangyiyunSessionManager] 登录超时，请检查登录状态")
        
        driver.quit()
    
    def _check_login_status(self, driver):
        """检查是否已经登录"""
        try:
            # 检查是否存在用户头像、用户名等登录标识
            login_indicators = [
                "//img[contains(@class, 'avatar')]",
                "//img[contains(@class, 'user')]",
                "//div[contains(@class, 'avatar')]",
                "//div[contains(@class, 'user')]",
                "//a[contains(@class, 'avatar')]",
                "//a[contains(@class, 'user')]",
                "//span[contains(@class, 'user')]",
                "//div[contains(@class, 'userinfo')]",
                "//div[contains(@class, 'm-tophead')]"
            ]
            
            for indicator in login_indicators:
                try:
                    elements = driver.find_elements(By.XPATH, indicator)
                    for element in elements:
                        if element.is_displayed():
                            print(f"[WangyiyunSessionManager] 检测到登录标识: {indicator}")
                            return True
                except:
                    continue
            
            # 检查是否不存在登录按钮
            login_buttons = [
                "//a[contains(text(), '登录')]",
                "//a[contains(text(), '注册')]",
                "//button[contains(text(), '登录')]",
                "//button[contains(text(), '注册')]",
                "//span[contains(text(), '登录')]",
                "//span[contains(text(), '注册')]"
            ]
            
            for button in login_buttons:
                try:
                    elements = driver.find_elements(By.XPATH, button)
                    for element in elements:
                        if element.is_displayed():
                            print(f"[WangyiyunSessionManager] 检测到登录按钮: {button}")
                            return False  # 如果看到登录按钮，说明未登录
                except:
                    continue
            
            # 检查页面标题
            title = driver.title.lower()
            if "登录" in title or "sign in" in title or "login" in title:
                print(f"[WangyiyunSessionManager] 页面标题包含登录关键词: {title}")
                return False
            
            # 检查页面源码中是否包含用户信息
            page_source = driver.page_source
            if "m-tophead" in page_source or "userinfo" in page_source:
                print("[WangyiyunSessionManager] 页面源码中包含用户信息")
                return True
            
            # 如果既没有登录按钮，也没有明确的登录页面标题，可能已登录
            print("[WangyiyunSessionManager] 未检测到明确的登录状态，假设已登录")
            return True
            
        except Exception as e:
            print(f"[WangyiyunSessionManager] 检查登录状态时出错: {e}")
            return False

class WangyiyunParser(BaseSummarizer):
    def __init__(self):
        self.audio_url = None
        self.session_manager = WangyiyunSessionManager()
        self.driver = None
        
    def _init_edge_driver(self):
        """初始化Edge浏览器驱动，继承基类配置并添加网易云特有设置"""
        # 获取网易云特有的配置
        browser_profile_dir = self.session_manager.browser_profile_dir
        
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

    def get_audio_info(self, url):
        """获取网易云播客的音频信息"""
        if self.driver is None:
            self._init_edge_driver()
            
        try:
            print(f"[INFO] 正在访问网易云播客页面: {url}")
            self.driver.get(url)
            
            # 等待页面完全加载，特别是单页应用的内容
            print("[INFO] 等待页面完全加载...")
            time.sleep(5)  # 增加等待时间
            
            # 检查是否有iframe，如果有则切换到iframe
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                print(f"[INFO] 检测到 {len(iframes)} 个iframe，尝试切换到内容iframe...")
                # 找到内容iframe（通常是g_iframe）
                content_iframe = None
                for iframe in iframes:
                    iframe_id = iframe.get_attribute("id")
                    if iframe_id == "g_iframe" or "content" in iframe_id.lower():
                        content_iframe = iframe
                        break
                
                if content_iframe:
                    print("[INFO] 切换到内容iframe...")
                    self.driver.switch_to.frame(content_iframe)
                    time.sleep(3)  # 等待iframe内容加载
                else:
                    print("[INFO] 未找到内容iframe，尝试第一个iframe...")
                    self.driver.switch_to.frame(iframes[0])
                    time.sleep(3)
            else:
                print("[INFO] 未检测到iframe，继续在主页面处理...")
            
            # 尝试滚动页面以触发更多内容加载
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # 检查是否需要登录
            if self._check_login_required():
                print("[INFO] 检测到需要登录，正在执行登录流程...")
                self.driver.quit()
                self.session_manager.manual_login()
                self._init_edge_driver()
                self.driver.get(url)
                time.sleep(5)  # 重新加载后也等待更长时间
            else:
                print("[INFO] 检测到已登录状态，继续处理...")
            
            # 获取标题
            title = self.driver.title
            print(f"[INFO] 页面标题: {title}")
            
            # 调试：打印当前页面的部分HTML结构
            try:
                page_source = self.driver.page_source
                print(f"[INFO] 当前页面源码长度: {len(page_source)}")
                if len(page_source) > 1000:
                    print(f"[INFO] 页面源码前1000字符: {page_source[:1000]}")
                else:
                    print(f"[INFO] 完整页面源码: {page_source}")
            except Exception as e:
                print(f"[INFO] 获取页面源码失败: {e}")
            
            # 点击播放按钮触发音频请求
            if self._click_play_button():
                print("[INFO] 播放按钮点击成功，等待音频请求...")
                
                # 等待更长时间让音频开始加载
                print("[INFO] 等待音频开始加载...")
                time.sleep(8)  # 增加等待时间
                
                # 尝试多次点击播放按钮，确保音频开始播放
                print("[INFO] 尝试多次点击播放按钮...")
                for i in range(3):
                    try:
                        self.driver.switch_to.frame(self.driver.find_element(By.ID, "g_iframe"))
                        play_button = self.driver.find_element(By.XPATH, "//a[@data-res-action='play']")
                        if play_button.is_displayed():
                            play_button.click()
                            print(f"[INFO] 第{i+1}次点击播放按钮")
                            time.sleep(3)
                    except Exception as e:
                        print(f"[ERROR] 第{i+1}次点击播放按钮失败: {e}")
                        break
                
                # 切换回主页面来捕获音频请求（音频请求通常在主页面）
                try:
                    self.driver.switch_to.default_content()
                    print("[INFO] 已切换回主页面，准备捕获音频请求...")
                    time.sleep(3)
                except Exception as e:
                    print(f"[ERROR] 切换回主页面失败: {e}")
                
                # 等待并捕获音频URL
                self._capture_audio_url()
            else:
                print("[ERROR] 播放按钮点击失败，尝试直接捕获音频URL...")
                # 即使播放按钮点击失败，也尝试捕获音频URL
                self._capture_audio_url()
            
            # 获取简介
            description = self._extract_description()
            
            if self.audio_url:
                result = {
                    "audio_url": self.audio_url,
                    "title": title,
                    "description": description
                }
                print(f"\n[INFO] 成功获取网易云播客信息:")
                print(f"    标题: {title}")
                print(f"    音频URL: {self.audio_url}")
                print(f"    简介长度: {len(description)} 字符")
                if description:
                    print(f"    简介预览: {description[:100]}...")
                else:
                    print(f"    简介: 无")
                return result
            else:
                raise Exception("未找到音频直链")
                
        except Exception as e:
            print(f"[ERROR] 获取网易云播客信息失败: {e}")
            raise Exception(f"获取网易云播客信息失败: {e}")
        finally:
            if self.driver:
                try:
                    # 切换回主页面
                    self.driver.switch_to.default_content()
                except:
                    pass
                self.driver.quit()
                self.driver = None

    def _check_login_required(self):
        """检查是否需要登录"""
        try:
            print("[INFO] 开始检查登录状态...")
            
            # 首先检查是否存在用户头像等已登录标识（优先级更高）
            avatar_indicators = [
                "//img[contains(@class, 'avatar')]",
                "//img[contains(@class, 'user')]",
                "//div[contains(@class, 'avatar')]",
                "//div[contains(@class, 'user')]",
                "//a[contains(@class, 'avatar')]",
                "//a[contains(@class, 'user')]",
                "//span[contains(@class, 'user')]",
                "//div[contains(@class, 'userinfo')]",
                "//div[contains(@class, 'm-tophead')]"
            ]
            
            for indicator in avatar_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    for element in elements:
                        if element.is_displayed():
                            print(f"[INFO] 检测到用户头像/用户信息元素: {indicator}")
                            return False  # 已登录
                except:
                    continue
            
            # 检查页面是否正常加载
            page_source = self.driver.page_source
            if "登录" in page_source or "注册" in page_source:
                print("[INFO] 页面源码中包含登录/注册关键词")
            else:
                print("[INFO] 页面源码中未发现登录/注册关键词")
            
            # 检查是否存在登录相关的元素
            login_indicators = [
                "//a[contains(text(), '登录')]",
                "//a[contains(text(), '注册')]",
                "//a[contains(text(), 'Sign in')]",
                "//a[contains(text(), 'Sign up')]",
                "//div[contains(@class, 'login')]",
                "//div[contains(@class, 'signin')]",
                "//button[contains(text(), '登录')]",
                "//button[contains(text(), '注册')]",
                "//span[contains(text(), '登录')]",
                "//span[contains(text(), '注册')]"
            ]
            
            for indicator in login_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, indicator)
                    for element in elements:
                        if element.is_displayed():
                            print(f"[INFO] 检测到登录元素: {indicator}")
                            return True  # 需要登录
                except Exception as e:
                    continue
            
            # 检查页面标题是否包含登录相关关键词
            title = self.driver.title.lower()
            if "登录" in title or "sign in" in title or "login" in title:
                print(f"[INFO] 页面标题包含登录关键词: {title}")
                return True  # 需要登录
                
            print("[INFO] 未检测到明确的登录状态，假设已登录")
            return False  # 默认已登录（更保守的策略）
            
        except Exception as e:
            print(f"[ERROR] 检查登录状态时出错: {e}")
            return False  # 出错时假设已登录（避免不必要的登录流程）

    def _click_play_button(self):
        """点击播放按钮"""
        try:
            # 网易云播客播放按钮选择器
            play_button_selectors = [
                "//a[@data-res-action='play']",
                "//a[contains(@class, 'u-btni-play')]",
                "//a[contains(@class, 'play')]",
                "//button[contains(@class, 'play')]",
                "//div[contains(@class, 'play')]",
                "//i[contains(text(), '播放')]/..",
                "//span[contains(text(), '播放')]/..",
                "//a[contains(text(), '播放')]",
                # 播放条中的播放按钮
                "//a[@data-action='play']",
                "//a[contains(@class, 'ply')]",
                "//a[contains(@class, 'j-flag') and contains(@class, 'ply')]",
                # 更通用的选择器
                "//a[contains(@title, '播放')]",
                "//a[contains(@title, '暂停')]"
            ]
            
            for selector in play_button_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed():
                            print(f"[INFO] 找到播放按钮: {selector}")
                            # 尝试多种点击方式
                            try:
                                element.click()
                            except:
                                try:
                                    self.driver.execute_script("arguments[0].click();", element)
                                except:
                                    continue
                            
                            print("[INFO] 已点击播放按钮")
                            time.sleep(5)  # 增加等待时间
                            return True
                except Exception as e:
                    continue
                    
            print("[ERROR] 未找到可用的播放按钮")
            return False
        except Exception as e:
            print(f"[ERROR] 点击播放按钮时出错: {e}")
            return False

    def _capture_audio_url(self):
        """捕获音频URL"""
        try:
            print("[INFO] 开始捕获音频URL...")
            
            # 多次尝试捕获音频URL
            for attempt in range(3):
                print(f"[INFO] 第{attempt + 1}次尝试捕获音频URL...")
                
                # 等待音频请求完成
                print("[INFO] 等待音频请求完成...")
                time.sleep(8)  # 增加等待时间
            
                # 使用selenium-wire捕获音频请求
                all_requests = [r for r in self.driver.requests if r.response]
                print(f"[INFO] 总共捕获到 {len(all_requests)} 个网络请求")
                
                # 打印网易云相关的请求，帮助调试
                music_requests = [r for r in all_requests if "music.126.net" in r.url]
                print(f"[INFO] 找到 {len(music_requests)} 个网易云相关请求")
                
                # 打印所有网易云请求，帮助调试
                for i, req in enumerate(music_requests):
                    print(f"[INFO] 网易云请求 {i+1}: {req.url}")
                
                # 网易云音频URL模式：更精确的匹配
                audio_requests = []
                for req in all_requests:
                    url = req.url
                    # 检查是否是音频请求
                    if ("music.126.net" in url and 
                        (".mp3" in url or 
                         "ymusic" in url or 
                         "obj" in url or
                         "w5zDlMODwrDDiGjCn8Ky" in url or
                         "vuutv=" in url)):  # vuutv参数是网易云音频的特征
                        audio_requests.append(req)
                
                print(f"[INFO] 找到 {len(audio_requests)} 个网易云音频请求")
                
                if audio_requests:
                    # 选择最长的URL（通常为主音频）
                    audio_requests = sorted(audio_requests, key=lambda r: len(r.url), reverse=True)
                    self.audio_url = audio_requests[0].url
                    print(f"[INFO] selenium-wire 捕获到音频URL: {self.audio_url}")
                    return True
                else:
                    # 尝试查找其他可能的网易云音频URL模式
                    audio_patterns = ["ymusic", "obj", "w5zDlMODwrDDiGjCn8Ky", "vuutv"]
                    for pattern in audio_patterns:
                        pattern_requests = [r for r in all_requests if pattern in r.url]
                        if pattern_requests:
                            print(f"[INFO] 找到包含 '{pattern}' 的请求: {len(pattern_requests)} 个")
                            for req in pattern_requests[:3]:  # 显示前3个
                                print(f"[INFO] {pattern} 请求: {req.url}")
                    
                    print("[ERROR] selenium-wire 未能捕获到音频URL")
                    
                    # 尝试从播放器元素中直接获取音频URL
                    print("[INFO] 尝试从播放器元素中获取音频URL...")
                    if self._get_audio_url_from_player():
                        return True
                    
                    # 如果这次尝试失败，等待一下再试
                    if attempt < 2:  # 不是最后一次尝试
                        print(f"[INFO] 第{attempt + 1}次尝试失败，等待5秒后重试...")
                        time.sleep(5)
                        continue
                    
                    return False
        except Exception as e:
            print(f"[ERROR] 捕获音频URL时出错: {e}")
            return False

    def _extract_description(self):
        """提取播客简介"""
        try:
            description = ""
            
            # 先尝试点击"展开"按钮
            try:
                expand_selectors = [
                    "//a[@data-action='spread']",
                    "//a[contains(text(), '展开')]",
                    "//a[contains(@class, 'spread')]"
                ]
                
                for selector in expand_selectors:
                    try:
                        expand_button = self.driver.find_element(By.XPATH, selector)
                        if expand_button.is_displayed():
                            print(f"[INFO] 找到展开按钮: {selector}")
                            expand_button.click()
                            time.sleep(2)
                            print("[INFO] 已点击展开按钮")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"[ERROR] 点击展开按钮时出错: {e}")
            
            # 获取简介内容
            try:
                # 尝试多个可能的简介选择器
                description_selectors = [
                    "//p[@id='full-description']",
                    "//div[contains(@class, 'description')]",
                    "//div[contains(@class, 'intro')]",
                    "//p[contains(@class, 's-fc3')]",
                    "//div[contains(@class, 'content')]",
                    # 更多可能的简介选择器
                    "//div[contains(@class, 'desc')]",
                    "//div[contains(@class, 'summary')]",
                    "//div[contains(@class, 'detail')]",
                    "//p[contains(@class, 'desc')]",
                    "//p[contains(@class, 'intro')]",
                    # 通用文本内容
                    "//div[contains(@class, 'text')]",
                    "//div[contains(@class, 'info')]"
                ]
                
                for selector in description_selectors:
                    try:
                        desc_elem = self.driver.find_element(By.XPATH, selector)
                        description = desc_elem.text.strip()
                        if description:
                            print(f"[INFO] 成功获取简介，长度: {len(description)} 字符")
                            return description
                    except:
                        continue
                        
                print("[ERROR] 未找到简介内容")
                return ""
                
            except Exception as e:
                print(f"[ERROR] 获取简介内容时出错: {e}")
                return ""
                
        except Exception as e:
            print(f"[ERROR] 提取简介时出错: {e}")
            return ""

    def _get_audio_url_from_player(self):
        """从播放器元素中直接获取音频URL"""
        try:
            # 尝试从audio元素中获取src
            audio_elements = self.driver.find_elements(By.TAG_NAME, "audio")
            for audio in audio_elements:
                src = audio.get_attribute("src")
                if src and "music.126.net" in src:
                    self.audio_url = src
                    print(f"[INFO] 从audio元素获取到音频URL: {self.audio_url}")
                    return True
            
            # 尝试从video元素中获取src
            video_elements = self.driver.find_elements(By.TAG_NAME, "video")
            for video in video_elements:
                src = video.get_attribute("src")
                if src and "music.126.net" in src:
                    self.audio_url = src
                    print(f"[INFO] 从video元素获取到音频URL: {self.audio_url}")
                    return True
            
            # 尝试从播放器相关的div中获取data属性
            player_selectors = [
                "//div[contains(@class, 'player')]",
                "//div[contains(@class, 'audio')]",
                "//div[contains(@class, 'media')]",
                "//div[@id='g_player']",
                "//div[contains(@class, 'm-playbar')]",
                "//div[contains(@class, 'play')]",
                "//div[contains(@class, 'm-pbar')]"
            ]
            
            for selector in player_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        # 检查各种可能的data属性
                        for attr in ['data-src', 'data-url', 'data-audio', 'data-music', 'data-res-id', 'data-res-type']:
                            value = element.get_attribute(attr)
                            if value and "music.126.net" in value:
                                self.audio_url = value
                                print(f"[INFO] 从播放器元素获取到音频URL: {self.audio_url}")
                                return True
                        
                        # 检查innerHTML中是否包含音频URL
                        try:
                            inner_html = element.get_attribute('innerHTML')
                            if inner_html and "music.126.net" in inner_html:
                                # 尝试从innerHTML中提取音频URL
                                import re
                                audio_pattern = r'https://[^"\']*music\.126\.net[^"\']*\.mp3[^"\']*'
                                matches = re.findall(audio_pattern, inner_html)
                                if matches:
                                    self.audio_url = matches[0]
                                    print(f"[INFO] 从播放器innerHTML获取到音频URL: {self.audio_url}")
                                    return True
                        except:
                            pass
                except:
                    continue
            
            print("[ERROR] 从播放器元素中未找到音频URL")
            return False
            
        except Exception as e:
            print(f"[ERROR] 从播放器元素获取音频URL时出错: {e}")
            return False

if __name__ == "__main__":
    url = "https://music.163.com/#/program?id=3079839307"
    parser = WangyiyunParser()
    try:
        info = parser.get_audio_info(url)
        print(info)
    except Exception as e:
        print(f"[ERROR] 发生错误: {e}") 