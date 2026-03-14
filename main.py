import argparse
import sys
import warnings

# 抑制 pkg_resources 相关的警告
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")

from dependency_check import check_dependencies
from zhihu import ZhihuSummarizer
from xiaohongshu import XiaohongshuSummarizer
from weixin import WeixinSummarizer
from util.process_url import process_url
from elsepage import ElsepageSummarizer

def main():
    check_dependencies()
    parser = argparse.ArgumentParser(description='网页内容摘要生成工具（豆包大模型版）')
    parser.add_argument('url', help='要处理的网页URL')
    parser.add_argument('--force-login', action='store_true', help='强制重新登录')
    parser.add_argument('--no-login', action='store_true', help='跳过登录，直接以游客身份访问')
    # 从配置文件获取默认值
    from util.config_manager import get_doubao_config
    doubao_config = get_doubao_config()
    default_api_key = doubao_config.get('api_key', '')
    default_model = doubao_config.get('model', '')
    
    parser.add_argument('--key', help='API密钥', default=default_api_key)
    parser.add_argument('--model', help='模型名称', default=default_model)
    parser.add_argument('--output', help='输出文件路径')
    args = parser.parse_args()
    
    url = args.url
    
    # 根据URL判断平台
    if "xiaohongshu.com" in url or "xhslink.com" in url:
        print("[INFO] 检测到小红书链接")
        summarizer = XiaohongshuSummarizer()
        if args.force_login:
            print("[INFO] 用户选择强制重新登录")
            summarizer.session_manager.manual_login()

    elif "zhihu.com" in url:
        print("[INFO] 检测到知乎链接")
        summarizer = ZhihuSummarizer()
        if args.force_login:
            print("[INFO] 用户选择强制重新登录")
            summarizer.session_manager.manual_login()

    elif "mp.weixin.qq.com" in url:
        print("[INFO] 检测到微信公众号链接")
        summarizer = WeixinSummarizer()
        if args.force_login:
            print("[INFO] 用户选择强制重新登录")
            summarizer.session_manager.manual_login()

    else:
        summarizer = ElsepageSummarizer()

    # 无论何种网页，先检测 Edge 驱动与浏览器版本是否一致；不一致则直接中止并给出手动替换提示
    try:
        from util.edge_driver_manager import ensure_edge_driver
        ensure_edge_driver()
    except RuntimeError as e:
        print(f"\n[ABORT] {e}")
        sys.exit(1)

    # 处理URL
    summary = process_url(summarizer, args.url, args.key, args.model, args.output)
    
    if summary:
        print("\n[INFO] 摘要预览:")
        print(summary[:500] + "..." if len(summary) > 500 else summary)
    else:
        print("[ERROR] 处理失败")

if __name__ == "__main__":
    main() 