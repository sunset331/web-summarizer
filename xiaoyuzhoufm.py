from base import BaseSummarizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import time
import os

class XiaoyuzhouFMParser(BaseSummarizer):
    def __init__(self):
        super().__init__()
        
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

    def get_audio_info(self, url):
        self._init_edge_driver()
        self.driver.get(url)
        time.sleep(5)  # 等待页面加载

        # 新增：尝试点击“展开”按钮以加载完整Show Notes
        try:
            expand_button = self.driver.find_element(By.CSS_SELECTOR, ".expand-wrap .expand")
            if expand_button and expand_button.is_displayed():
                print("[INFO] 检测到“展开”按钮，正在尝试点击...")
                expand_button.click()
                time.sleep(2)  # 等待内容加载
                print("[INFO] “展开”按钮已点击。")
        except Exception as e:
            print(f"[ERROR] 未找到“展开”按钮或点击失败，将继续尝试直接提取。错误: {e}")

        try:
            audio_elem = self.driver.find_element(By.TAG_NAME, "audio")
            audio_url = audio_elem.get_attribute("src")
            title = self.driver.title

            # 新增：获取简介文本
            description = ""
            try:
                content_elem = self.driver.find_element(By.CSS_SELECTOR, ".sn-content")
                description = content_elem.text
            except Exception as e:
                print(f"[ERROR] 未找到简介内容或获取失败: {e}")

            self.driver.quit()
            if audio_url:
                return {
                    "audio_url": audio_url,
                    "title": title,
                    "description": description  # 返回简介文本
                }
            else:
                raise Exception("[ERROR] 未找到音频直链")
        except Exception as e:
            self.driver.quit()
            raise Exception(f"[ERROR] 未找到音频直链: {e}") 