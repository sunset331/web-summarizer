from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager

try:
    from seleniumwire.webdriver import Edge as WireEdge
except ImportError:
    WireEdge = None

class BaseSummarizer:
    # 统一的桌面版User-Agent
    DESKTOP_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
    
    def __init__(self):
        self.driver = None

    def _get_base_edge_options(self):
        """获取基础Edge选项配置"""
        edge_options = EdgeOptions()
        
        # 基础反检测设置
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_argument("--start-maximized")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # 确保使用桌面版用户代理
        edge_options.add_argument(f'--user-agent={self.DESKTOP_USER_AGENT}')
        
        # 增强稳定性设置
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--disable-software-rasterizer")
        edge_options.add_argument("--disable-extensions")
        edge_options.add_argument("--disable-plugins")
        edge_options.add_argument("--disable-images")  # 可选：禁用图片加载提高速度
        edge_options.add_argument("--disable-javascript")  # 可选：禁用JS提高稳定性
        edge_options.add_argument("--disable-web-security")
        edge_options.add_argument("--allow-running-insecure-content")
        edge_options.add_argument("--disable-features=VizDisplayCompositor")
        
        # 内存和性能优化
        edge_options.add_argument("--memory-pressure-off")
        edge_options.add_argument("--max_old_space_size=4096")
        
        # 禁用日志
        edge_options.add_argument("--log-level=3")
        edge_options.add_argument("--silent")
        
        return edge_options

    def _init_edge_driver(self):
        """初始化标准Edge浏览器驱动"""
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

    def _find_local_msedgedriver(self):
        """
        查找本地msedgedriver.exe文件
        
        Returns:
            找到的驱动文件路径，如果未找到返回None
        """
        import os
        import subprocess
        
        # 可能的路径列表
        possible_paths = [
            # 项目根目录
            os.path.join(os.getcwd(), "msedgedriver.exe"),
            # 当前检测到的路径
            "D:\\edgedriver_win64\\msedgedriver.exe",
            # 系统PATH中的msedgedriver
            "msedgedriver.exe"
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path) or path == "msedgedriver.exe":
                    # 检查版本兼容性
                    if self._check_driver_version(path):
                        return path
            except Exception as e:
                print(f"[DEBUG] 检查路径 {path} 时出错: {e}")
                continue
        
        return None
    
    def _check_driver_version(self, driver_path):
        """
        检查驱动版本是否与Edge浏览器兼容
        
        Args:
            driver_path: 驱动文件路径
            
        Returns:
            是否兼容
        """
        try:
            import subprocess
            import re
            
            # 运行msedgedriver --version
            if driver_path == "msedgedriver.exe":
                result = subprocess.run([driver_path, "--version"], 
                                     capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run([driver_path, "--version"], 
                                     capture_output=True, text=True)
            
            if result.returncode == 0:
                version_output = result.stdout.strip()
                print(f"[INFO] 检测到Edge驱动版本: {version_output}")
                
                # 提取版本号
                version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_output)
                if version_match:
                    major_version = int(version_match.group(1))
                    # Edge 79+ (Chromium内核) 都兼容
                    if major_version >= 79:
                        return True
                
                return True  # 如果无法解析版本，假设兼容
            else:
                print(f"[WARNING] 无法获取驱动版本: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[WARNING] 检查驱动版本时出错: {e}")
            return False

    def _close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _init_edge_wire_driver(self):
        """初始化selenium-wire Edge浏览器驱动"""
        edge_options = self._get_base_edge_options()
        
        wire_options = {
            'disable_encoding': True,
        }
        
        if WireEdge is None:
            raise ImportError('[ERROR] 请先安装selenium-wire: pip install selenium-wire')
        
        try:
            # 首先尝试使用本地msedgedriver
            local_driver_path = self._find_local_msedgedriver()
            
            if local_driver_path:
                print(f"[INFO] 使用本地Edge驱动 (selenium-wire): {local_driver_path}")
                self.driver = WireEdge(
                    service=Service(local_driver_path),
                    options=edge_options,
                    seleniumwire_options=wire_options
                )
            else:
                print("[WARNING] 未找到本地Edge驱动，尝试自动下载...")
                # 如果本地没有，尝试自动下载（可能失败）
                self.driver = WireEdge(
                    service=Service(EdgeChromiumDriverManager().install()),
                    options=edge_options,
                    seleniumwire_options=wire_options
                )
            
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
            )
            # 设置窗口大小为桌面版
            self.driver.set_window_size(1920, 1080)
            
        except Exception as e:
            print(f"[ERROR] selenium-wire Edge浏览器初始化失败: {e}")
            if "Could not reach host" in str(e) or "getaddrinfo failed" in str(e):
                print("[ERROR] 网络连接失败，无法自动下载Edge驱动")
                print("[SOLUTION] 请确保已下载msedgedriver.exe并放置在以下位置之一：")
                print("  1. 项目根目录")
                print("  2. D:\\edgedriver_win64\\ (当前检测到的路径)")
                print("  3. 系统PATH中的任何目录")
            raise 