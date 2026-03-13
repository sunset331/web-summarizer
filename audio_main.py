import os
from xiaoyuzhoufm import XiaoyuzhouFMParser
from util.audio_utils import (
    download_audio, 
    extract_all_text_from_json, 
    preprocess_order_result, 
    xunfei_asr_long,
    convert_to_wav
)
import json
import datetime
from util.hot_words import extract_keywords_for_hotword
from ximalaya import XimalayaParser
from wangyiyun import WangyiyunParser

# 从配置文件获取讯飞认证信息
from util.config_manager import get_xunfei_config
xunfei_config = get_xunfei_config()
XUNFEI_APPID = xunfei_config.get('appid')
XUNFEI_SECRET = xunfei_config.get('secret')

def get_save_folder(title, platform="unknown"):
    """通用的文件夹生成函数，根据平台和标题动态生成文件夹名"""
    safe_title = "".join([c for c in title if c.isalnum() or c in '_-（）()【】 ']).strip().replace(' ', '_')
    now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = os.path.join(os.path.expanduser('~'), 'Desktop', f'{platform}_{safe_title}_{now_str}')
    os.makedirs(folder, exist_ok=True)
    return folder

if __name__ == "__main__":
    url = input("请输入音频链接：")
    # 网页标题作为文件夹名
    if "xiaoyuzhoufm.com" in url:
        parser = XiaoyuzhouFMParser()
        platform = "xiaoyuzhoufm"
    elif "ximalaya.com" in url:
        parser = XimalayaParser()
        platform = "ximalaya"
    elif "music.163.com" in url:
        parser = WangyiyunParser()
        platform = "wangyiyun"
    else:
        print("[ERROR] 暂不支持该平台")
        exit()
    info = parser.get_audio_info(url)
    folder = get_save_folder(info.get('title'), platform)

    # 从标题和简介中动态生成热词
    title_text = info.get("title", "")
    description_text = info.get("description", "")
    
    # 合并标题和简介
    combined_text = f"{title_text} {description_text}"
    dynamic_hot_words = extract_keywords_for_hotword(combined_text)
    
    folder_name = os.path.basename(folder)
    prefix = folder_name  # 统一前缀为文件夹名
    # 下载音频到专属文件夹，命名为 {prefix}_origin.原始扩展名
    audio_ext = os.path.splitext(info['audio_url'].split('/')[-1].split('?')[0])[1]
    audio_filename = f'{prefix}_origin{audio_ext}'
    audio_path = os.path.join(folder, audio_filename)
    download_audio(info['audio_url'], folder, filename=audio_filename)
    print("[INFO] 已下载到：", audio_path)
    # 转换为wav，命名为 {prefix}_16k.wav
    wav_path = os.path.join(folder, f'{prefix}_16k.wav')
    convert_to_wav(audio_path, wav_path)
    print("[INFO] 已转换为wav：", wav_path)
    try:
        os.remove(audio_path)
        print(f"[INFO] 已删除原始音频文件：{audio_path}")
    except Exception as e:
        print(f"[ERROR] 删除原始音频文件失败：{e}")
    file_path = wav_path
    
    # 调用新版util.audio_utils的转写流程
    text, result_json = xunfei_asr_long(file_path, XUNFEI_APPID, XUNFEI_SECRET, hot_word=dynamic_hot_words)
    # 先预处理orderResult字符串为json对象
    result_json = preprocess_order_result(result_json)
    # 保存处理后的json
    json_path = os.path.join(folder, f'{prefix}_raw.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result_json, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 已保存原始转写json到: {json_path}")
    # 提取带时间戳的文本内容
    timestamped_texts = []
    
    # 从JSON中提取每句话及其时间戳
    if 'content' in result_json and 'orderResult' in result_json['content']:
        order_result = result_json['content']['orderResult']
        if 'lattice' in order_result:
            for lattice_item in order_result['lattice']:
                if 'json_1best' in lattice_item:
                    json_1best = lattice_item['json_1best']
                    if 'st' in json_1best and 'rt' in json_1best['st']:
                        st = json_1best['st']
                        bg = st.get('bg', 0)  # 开始时间（毫秒）
                        ed = st.get('ed', 0)  # 结束时间（毫秒）
                        
                        # 提取文本内容
                        text_content = ""
                        if 'rt' in st and isinstance(st['rt'], list):
                            for rt_item in st['rt']:
                                if 'ws' in rt_item and isinstance(rt_item['ws'], list):
                                    for ws_item in rt_item['ws']:
                                        if 'cw' in ws_item and isinstance(ws_item['cw'], list):
                                            text_content += "".join([cw_item.get('w', '') for cw_item in ws_item['cw']])
                        
                        if text_content.strip():
                            # 转换时间戳为易读格式
                            start_seconds = int(bg) / 1000.0
                            end_seconds = int(ed) / 1000.0
                            
                            if start_seconds < 60:
                                start_time = f"{start_seconds:.1f}秒"
                            else:
                                start_min = int(start_seconds // 60)
                                start_sec = int(start_seconds % 60)
                                start_time = f"{start_min}分{start_sec}秒"
                            
                            if end_seconds < 60:
                                end_time = f"{end_seconds:.1f}秒"
                            else:
                                end_min = int(end_seconds // 60)
                                end_sec = int(end_seconds % 60)
                                end_time = f"{end_min}分{end_sec}秒"
                            
                            # 格式：文本内容 [时间范围：开始时间-结束时间]
                            timestamped_line = f"{text_content} [时间范围：{start_time}-{end_time}]"
                            timestamped_texts.append(timestamped_line)
    
    # 保存带时间戳的文本
    timestamped_text = '\n'.join(timestamped_texts)
    text_path = os.path.join(folder, f'{prefix}_text.txt')
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(timestamped_text)
    print(f"[INFO] 已提取带时间戳的文本内容到 {text_path}")
    
    # 同时保存纯文本版本（用于摘要生成）
    pure_text = '\n'.join([t.split(' [时间范围：')[0] for t in timestamped_texts if t.strip()])
    # 生成分块摘要
    summary_path = os.path.join(folder, f'{prefix}_summary.md')
    if pure_text and pure_text.strip():
        # 使用专门的音频摘要函数，传入带时间戳的文本
        from util.generate_summary import generate_audio_summary
        
        # 直接传入带时间戳的文本，大模型可以直接看到时间信息
        summary = generate_audio_summary(timestamped_text, "", "")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"[INFO] 音频摘要已保存到 {summary_path}")
    else:
        print("[ERROR] 未获取到有效转写文本，无法生成摘要。") 