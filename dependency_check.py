import sys


def check_dependencies():
    """
    统一检查项目运行依赖（CLI + 抓取 + 音视频 + Web 服务）。
    """
    # key: python import 名称, value: pip 安装包名
    required_packages = {
        # 抓取/摘要核心
        "requests": "requests",
        "bs4": "beautifulsoup4",
        "trafilatura": "trafilatura",
        "openai": "openai",
        "PIL": "Pillow",
        # Selenium 相关
        "selenium": "selenium",
        "seleniumwire": "selenium-wire",
        # 音视频相关
        "pydub": "pydub",
        "textrank4zh": "textrank4zh",
        "cv2": "opencv-python",
        "imutils": "imutils",
        "numpy": "numpy",
        # Web 服务
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "multipart": "python-multipart",
    }

    missing_imports = []
    missing_pip_names = []
    for module_name, pip_name in required_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_imports.append(module_name)
            missing_pip_names.append(pip_name)

    if missing_imports:
        pip_unique = " ".join(sorted(set(missing_pip_names)))
        print(f"[ERROR] 依赖缺失: {', '.join(sorted(set(missing_imports)))}")
        print("[INFO] 请安装后重试。")
        print(f"[INFO] 推荐命令: pip install {pip_unique}")
        sys.exit(1)