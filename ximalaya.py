from base import BaseSummarizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import time
import os

class XimalayaParser(BaseSummarizer):
    def __init__(self):
        super().__init__()
        self.audio_url = None  # 用于存储捕获的音频URL
        
    def _init_edge_driver(self):
        """初始化Edge浏览器驱动"""
        edge_options = self._get_base_edge_options()
        
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

    def _slow_scroll_to_bottom(self, driver, scroll_pause_time=0.5, scroll_step=300):
        """缓慢滚动到底部"""
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script(f"window.scrollBy(0, {scroll_step});")
            time.sleep(scroll_pause_time)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def get_audio_info(self, url):
        self._init_edge_driver()
        
        try:
            self.driver.get(url)
            time.sleep(2)

            # 播放按钮选择器逻辑（保留）
            play_btn_selectors = [
                ".play-btn.U_s",
                ".play-btn",
                ".svg-icon-play",
                "[class*='play']",
                "button[aria-label='播放']"
            ]
            for _ in range(2):
                play_button = None
                for selector in play_btn_selectors:
                    try:
                        play_button = self.driver.find_element("css selector", selector)
                        if play_button.is_displayed():
                            play_button.click()
                            print(f"[INFO] 已点击播放按钮: {selector}")
                            time.sleep(2)
                            break
                    except Exception:
                        continue
                if not play_button:
                    print("[ERROR] 未找到可用的播放按钮")

            # 延长等待时间，确保音频请求被捕获
            time.sleep(10)

            # 用 selenium-wire 捕获所有音频请求
            audio_requests = [r for r in self.driver.requests if r.response and r.url.split('?')[0].endswith((".mp3", ".m4a", ".aac"))]
            if audio_requests:
                # 选最长的URL（通常为主音频）
                audio_requests = sorted(audio_requests, key=lambda r: len(r.url), reverse=True)
                self.audio_url = audio_requests[0].url
                print(f"[INFO] selenium-wire 捕获到音频URL: {self.audio_url}")
            else:
                print("[ERROR] selenium-wire 未能捕获到音频URL")

            # 获取标题
            title = self.driver.title

            # 简介提取逻辑（保留）
            description = ""
            try:
                # 先点击"更多全部"按钮展开简介
                try:
                    expand_btn = self.driver.find_element("css selector", ".more-intro-wrapper")
                    if expand_btn and expand_btn.is_displayed():
                        print("[INFO] 检测到'更多全部'按钮，正在点击...")
                        expand_btn.click()
                        time.sleep(2)  # 增加等待时间
                        print("[INFO] '更多全部'按钮已点击。")
                except Exception as e:
                    print(f"[ERROR] 未找到'更多全部'按钮或点击失败，将直接提取简介。错误: {e}")

                # 缓慢滚动到底部，确保所有内容都加载
                print("[INFO] 正在缓慢滚动页面...")
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                while True:
                    # 滚动到底部
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)  # 等待内容加载
                    
                    # 计算新的页面高度
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height
                print("[INFO] 页面滚动完成")

                # 再等待一下，确保所有动态内容都加载完成
                time.sleep(2)

                # 获取简介正文
                try:
                    intro_elem = self.driver.find_element("css selector", "article.intro")
                    description = intro_elem.text
                    print(f"[INFO] 成功获取简介，长度: {len(description)} 字符")
                except Exception as e:
                    print(f"[ERROR] 未找到简介内容或获取失败: {e}")
            except Exception as e:
                print(f"[ERROR] 简介获取过程中发生错误: {e}")

            if self.audio_url:
                result = {
                    "audio_url": self.audio_url,
                    "title": title,
                    "description": description
                }
                print(f"\n[INFO] 成功获取音频信息:")
                print(f"    标题: {title}")
                print(f"    音频URL: {self.audio_url}")
                print(f"    简介长度: {len(description)} 字符")
                if description:
                    print(f"    完整简介:")
                    print(f"    {'='*50}")
                    print(description)
                    print(f"    {'='*50}")
                else:
                    print(f"    简介: 无")
                return result
            else:
                raise Exception("[ERROR] 未找到音频直链")
                
        finally:
            self.driver.quit()

if __name__ == "__main__":
    url = "https://www.ximalaya.com/sound/868968480"
    parser = XimalayaParser()
    try:
        info = parser.get_audio_info(url)
        print(info)
    except Exception as e:
        print(f"[ERROR] 发生错误: {e}")