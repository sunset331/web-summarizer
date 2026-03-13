import sys

def check_dependencies():
    REQUIRED_MODULES = [
        'argparse', 'urllib.parse', 'requests', 'bs4', 'trafilatura', 'os', 're', 'hashlib', 'json',
        'datetime', 'time', 'random', 'selenium', 'webdriver_manager', 'seleniumwire',
    ]
    missing = []
    for mod in REQUIRED_MODULES:
        try:
            __import__(mod.split('.')[0])
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"[ERROR] 依赖缺失: 请先安装以下依赖: {', '.join(set(missing))}")
        print("[INFO] 推荐命令: pip install requests beautifulsoup4 trafilatura selenium webdriver-manager")
        sys.exit(1) 