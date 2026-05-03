import os
import json
import re
import argparse
from datetime import datetime
from typing import List, Dict, Tuple
import glob
import time

# 导入现有的工具函数
from util.audio_utils import xunfei_asr_long, preprocess_order_result

from util.audio_utils import convert_to_wav
from util.multimodal_summary import generate_multimodal_summary, fallback_text_summary

class MeetingTranscriber:
    def __init__(self, folder_path: str, appid: str = "", apisecret: str = "", doubao_api_key: str = ""):
        self.folder_path = folder_path
        
        # 从配置文件获取API配置
        from util.config_manager import get_xunfei_config, get_doubao_config
        xunfei_config = get_xunfei_config()
        doubao_config = get_doubao_config()
        
        self.appid = appid or xunfei_config.get('appid')
        self.apisecret = apisecret or xunfei_config.get('secret')
        self.doubao_api_key = doubao_api_key or doubao_config.get('api_key')
        self.audio_files = []
        self.image_files = []
        self.image_timestamps = {}
        
    def scan_folder(self):
        """扫描文件夹，获取音频文件和图片文件"""
        print(f"[INFO] 扫描文件夹: {self.folder_path}")
        
        # 获取音频文件
        audio_extensions = ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.flac', '*.ogg', '*.wma']
        for ext in audio_extensions:
            files = glob.glob(os.path.join(self.folder_path, ext))
            files.extend(glob.glob(os.path.join(self.folder_path, ext.upper())))
            # 去重
            for file in files:
                if file not in self.audio_files:
                    self.audio_files.append(file)
        
        # 获取图片文件
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.tiff']
        for ext in image_extensions:
            files = glob.glob(os.path.join(self.folder_path, ext))
            files.extend(glob.glob(os.path.join(self.folder_path, ext.upper())))
            # 去重
            for file in files:
                if file not in self.image_files:
                    self.image_files.append(file)
        
        print(f"[INFO] 找到 {len(self.audio_files)} 个音频文件")
        for audio_file in self.audio_files:
            print(f"  - {os.path.basename(audio_file)}")
        
        print(f"[INFO] 找到 {len(self.image_files)} 个图片文件")
        for image_file in self.image_files:
            print(f"  - {os.path.basename(image_file)}")
        
        # 解析图片文件名中的时间戳
        self._parse_image_timestamps()
        
    def _parse_image_timestamps(self):
        """解析图片文件名中的时间戳"""
        print("[INFO] 解析图片时间戳...")
        
        for image_path in self.image_files:
            filename = os.path.basename(image_path)
            print(f"[INFO] 正在解析图片: {filename}")
            
            # 尝试从文件名中提取时间戳
            # 支持多种格式：HHMMSS, HH:MM:SS, MM:SS, SS等
            timestamp_patterns = [
                r'(\d{2})(\d{2})(\d{2})',  # HHMMSS
                r'(\d{1,2}):(\d{2}):(\d{2})',  # HH:MM:SS
                r'(\d{1,2}):(\d{2})',  # MM:SS
                r'(\d+)',  # 纯秒数
            ]
            
            timestamp_found = False
            for i, pattern in enumerate(timestamp_patterns):
                match = re.search(pattern, filename)
                if match:
                    print(f"[INFO] 匹配到模式 {i+1}: {pattern}")
                    print(f"[INFO] 匹配结果: {match.groups()}")
                    
                    if len(match.groups()) == 3:  # HH:MM:SS 或 HHMMSS
                        hours = int(match.group(1))
                        minutes = int(match.group(2))
                        seconds = int(match.group(3))
                    elif len(match.groups()) == 2:  # MM:SS
                        hours = 0
                        minutes = int(match.group(1))
                        seconds = int(match.group(2))
                    else:  # 纯秒数
                        total_seconds = int(match.group(1))
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                    
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                    self.image_timestamps[image_path] = total_seconds
                    print(f"[+] 图片 {filename} -> {hours:02d}:{minutes:02d}:{seconds:02d} ({total_seconds}秒)")
                    timestamp_found = True
                    break  # 找到第一个匹配就停止
            
            if not timestamp_found:
                print(f"[ERROR] 图片 {filename} 未找到时间戳")
        
        print(f"[INFO] 成功解析 {len(self.image_timestamps)} 个图片时间戳")
        print(f"[INFO] 解析的图片时间戳: {self.image_timestamps}")
    
    def transcribe_audio(self, audio_path: str) -> Tuple[str, Dict]:
        """转写音频文件"""
        print(f"[INFO] 开始转写音频: {os.path.basename(audio_path)}")
        
        # 检查音频文件长度
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            duration_seconds = len(audio) / 1000.0
            print(f"[INFO] 音频文件长度: {duration_seconds:.1f}秒 ({duration_seconds/60:.1f}分钟)")
        except Exception as e:
            print(f"[ERROR] 无法获取音频长度: {e}")
            duration_seconds = None
        
        # 转换为WAV格式
        wav_path = os.path.splitext(audio_path)[0] + "_temp.wav"
        try:
            convert_to_wav(audio_path, wav_path)
            print(f"[INFO] 音频转换为WAV: {wav_path}")
        except Exception as e:
            print(f"[ERROR] 音频转换失败: {e}")
            return None, None
        
        # 调用讯飞转写API
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[INFO] 转写尝试 {attempt + 1}/{max_retries}")
                text, result_json = xunfei_asr_long(wav_path, self.appid, self.apisecret)
                
                # 预处理JSON结果
                result_json = preprocess_order_result(result_json)
                
                # 检查转写结果的时间范围
                if result_json and 'data' in result_json:
                    # 提取所有时间戳并计算范围
                    all_times = []
                    def extract_times(obj):
                        if isinstance(obj, dict):
                            for key, value in obj.items():
                                if key == 'bg' or key == 'ed':
                                    all_times.append(value)
                                elif isinstance(value, (dict, list)):
                                    extract_times(value)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_times(item)
                    
                    extract_times(result_json)
                    
                    if all_times:
                        max_time = max(all_times) / 1000.0  # 转换为秒
                        print(f"[INFO] 转写结果最大时间: {max_time:.1f}秒 ({max_time/60:.1f}分钟)")
                        
                        if duration_seconds and max_time < duration_seconds * 0.8:
                            print(f"[ERROR] 转写结果时间 ({max_time:.1f}s) 明显短于音频长度 ({duration_seconds:.1f}s)")
                            if attempt < max_retries - 1:
                                print(f"[INFO] 将重试转写...")
                                continue
                
                # 保存原始JSON
                json_path = os.path.splitext(audio_path)[0] + "_transcription.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result_json, f, ensure_ascii=False, indent=2)
                print(f"[INFO] 转写JSON已保存: {json_path}")
                
                # 清理临时文件
                if os.path.exists(wav_path):
                    os.remove(wav_path)
                
                return text, result_json
                
            except Exception as e:
                print(f"[ERROR] 音频转写失败 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print(f"[INFO] 将重试转写...")
                    time.sleep(5)  # 等待5秒后重试
                else:
                    print(f"[ERROR] 所有转写尝试都失败")
                    # 清理临时文件
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                    return None, None
        
        return None, None
    
    def json_to_srt(self, result_json: Dict, output_path: str) -> str:
        """将转写JSON转换为SRT格式"""
        print("[INFO] 转换JSON为SRT格式...")
        
        srt_content = []
        subtitle_index = 1
        
        # 从lattice格式中提取文本和时间戳
        def extract_lattice_segments(data):
            segments = []
            if isinstance(data, dict) and 'content' in data:
                content = data['content']
                if 'orderResult' in content:
                    order_result = content['orderResult']
                    if isinstance(order_result, dict) and 'lattice' in order_result:
                        lattice = order_result['lattice']
                        for item in lattice:
                            if isinstance(item, dict) and 'json_1best' in item:
                                json_1best = item['json_1best']
                                if isinstance(json_1best, dict) and 'st' in json_1best:
                                    st = json_1best['st']
                                    # 提取文本
                                    text_parts = []
                                    for rt in st.get('rt', []):
                                        for ws in rt.get('ws', []):
                                            for cw in ws.get('cw', []):
                                                text_parts.append(cw.get('w', ''))
                                    
                                    text = ''.join(text_parts)
                                    if text.strip():
                                        # 提取时间戳
                                        bg = int(st.get('bg', '0'))
                                        ed = int(st.get('ed', '0'))
                                        role_id = st.get('rl', '0')
                                        segments.append({
                                            'text': text,
                                            'bg': bg,
                                            'ed': ed,
                                            'role_id': role_id
                                        })
            return segments
        
        # 提取所有段落
        segments = extract_lattice_segments(result_json)
        print(f"[INFO] 提取到 {len(segments)} 个段落")
        
        # 按时间排序
        segments.sort(key=lambda x: x['bg'])
        
        # 生成SRT内容
        for segment in segments:
            # 转换时间戳（毫秒转秒）
            start_time = segment['bg'] / 1000.0
            end_time = segment['ed'] / 1000.0
            
            # 格式化时间戳
            start_timestamp = self._seconds_to_srt_time(start_time)
            end_timestamp = self._seconds_to_srt_time(end_time)
            
            # 添加角色标签
            text = segment['text']
            if segment['role_id'] != '0':
                text = f"[角色{segment['role_id']}]: {text}"
            
            # 添加SRT条目
            srt_content.append(f"{subtitle_index}")
            srt_content.append(f"{start_timestamp} --> {end_timestamp}")
            srt_content.append(text.strip())
            srt_content.append("")
            
            subtitle_index += 1
        
        # 保存SRT文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))
        
        print(f"[INFO] SRT文件已保存: {output_path}")
        print(f"[INFO] SRT文件时间范围: {segments[0]['bg']/1000:.1f}s - {segments[-1]['ed']/1000:.1f}s")
        return output_path
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def insert_image_links(self, srt_path: str) -> str:
        """在SRT文件中插入图片链接"""
        print("[INFO] 在SRT中插入图片链接...")
        
        # 读取SRT文件
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # 按字幕块分割
        subtitle_blocks = srt_content.strip().split('\n\n')
        modified_blocks = []
        
        print(f"[INFO] 图片时间戳: {self.image_timestamps}")
        print(f"[INFO] SRT文件总字幕块数: {len(subtitle_blocks)}")
        
        # 计算SRT文件的时间范围
        if subtitle_blocks:
            first_block = subtitle_blocks[0].split('\n')
            last_block = subtitle_blocks[-1].split('\n')
            if len(first_block) >= 2 and len(last_block) >= 2:
                start_time = self._parse_srt_time(first_block[1].split(' --> ')[0])
                end_time = self._parse_srt_time(last_block[1].split(' --> ')[1])
                print(f"[INFO] SRT文件时间范围: {start_time}s - {end_time}s")
        
        # 检查每个图片的时间戳
        for image_path, timestamp in self.image_timestamps.items():
            print(f"[INFO] 检查图片 {os.path.basename(image_path)} (时间:{timestamp}s)")
            
            # 找到最接近的字幕块
            closest_block = None
            min_diff = float('inf')
            
            for i, block in enumerate(subtitle_blocks):
                lines = block.split('\n')
                if len(lines) >= 2:
                    time_line = lines[1]
                    block_start_time = self._parse_srt_time(time_line.split(' --> ')[0])
                    time_diff = abs(timestamp - block_start_time)
                    
                    if time_diff < min_diff:
                        min_diff = time_diff
                        closest_block = i
            
            if closest_block is not None:
                print(f"[INFO] 图片 {os.path.basename(image_path)} 最接近字幕块 {closest_block+1} (差距:{min_diff}s)")
        
        for i, block in enumerate(subtitle_blocks):
            lines = block.split('\n')
            if len(lines) >= 3:
                # 解析时间戳
                time_line = lines[1]
                start_time = self._parse_srt_time(time_line.split(' --> ')[0])
                
                # 查找对应时间点的图片
                matching_images = []
                for image_path, timestamp in self.image_timestamps.items():
                    time_diff = abs(timestamp - start_time)
                    if time_diff <= 10:  # 扩大到10秒内的图片
                        relative_path = os.path.relpath(image_path, self.folder_path)
                        if relative_path not in matching_images:  # 避免重复添加
                            matching_images.append(relative_path)
                            print(f"[INFO] 字幕块 {i+1} (时间:{start_time}s) 匹配图片 {os.path.basename(image_path)} (时间:{timestamp}s, 差距:{time_diff}s)")
                
                # 在文本后添加图片链接
                if matching_images:
                    text_lines = lines[2:]
                    for image_path in matching_images:
                        text_lines.append(f"[IMAGE: {image_path}]")
                    lines[2:] = text_lines
                
                modified_blocks.append('\n'.join(lines))
            else:
                modified_blocks.append(block)
        
        # 保存修改后的SRT文件
        modified_srt_path = srt_path.replace('.srt', '_with_images.srt')
        with open(modified_srt_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(modified_blocks))
        
        print(f"[INFO] 带图片链接的SRT已保存: {modified_srt_path}")
        return modified_srt_path
    
    def _parse_srt_time(self, time_str: str) -> float:
        """解析SRT时间格式为秒数"""
        time_parts = time_str.replace(',', '.').split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds = float(time_parts[2])
        return hours * 3600 + minutes * 60 + seconds
    
    def generate_summary_with_images(self, srt_path: str, understand_images: bool = True) -> str:
        """生成包含图片理解的摘要"""
        print(f"[INFO] 生成摘要 (理解图片: {understand_images})...")
        
        # 读取SRT文件
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # 提取文本和图片路径
        text_content = []
        image_paths = []
        seen_images = set()  # 用于去重
        
        subtitle_blocks = srt_content.strip().split('\n\n')
        for block in subtitle_blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                # 提取文本内容
                text_lines = lines[2:]
                for line in text_lines:
                    if line.startswith('[IMAGE:'):
                        # 提取图片路径
                        image_match = re.search(r'\[IMAGE: (.*?)\]', line)
                        if image_match:
                            image_path = os.path.join(self.folder_path, image_match.group(1))
                            if os.path.exists(image_path) and image_path not in seen_images:
                                image_paths.append(image_path)
                                seen_images.add(image_path)
                                print(f"[INFO] 找到图片引用: {image_match.group(1)} -> {image_path}")
                            elif image_path in seen_images:
                                print(f"[INFO] 跳过重复图片: {image_match.group(1)}")
                            else:
                                print(f"[ERROR] 图片文件不存在: {image_path}")
                    else:
                        text_content.append(line)
        
        # 合并文本内容
        full_text = '\n'.join(text_content)
        
        print(f"[INFO] 总共找到 {len(image_paths)} 张唯一图片引用")
        for i, img_path in enumerate(image_paths):
            print(f"[INFO] 图片{i+1}: {os.path.basename(img_path)}")
        
        if understand_images and image_paths:
            # 理解图片内容并生成摘要
            print(f"[INFO] 使用多模态模型理解 {len(image_paths)} 张图片...")
            # 这里需要调用豆包多模态API
            summary = self._generate_multimodal_summary(full_text, image_paths)
        else:
            # 只根据文本生成摘要
            print("[INFO] 仅根据文本生成摘要...")
            summary = fallback_text_summary(full_text)
        
        # 保存摘要
        summary_path = os.path.join(self.folder_path, f"meeting_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(f"[INFO] 摘要已保存: {summary_path}")
        return summary_path
    
    def _generate_multimodal_summary(self, text: str, image_paths: List[str]) -> str:
        """调用豆包多模态API生成摘要"""
        try:
            return generate_multimodal_summary(text, image_paths, self.doubao_api_key)
        except Exception as e:
            print(f"[ERROR] 多模态摘要生成失败: {e}")
            # 降级到文本摘要
            return fallback_text_summary(text)
    
    def process_meeting(self, understand_images: bool = True):
        """处理整个会议转写流程"""
        print("=" * 50)
        print("会议转写处理开始")
        print("=" * 50)
        
        # 检查是否已经扫描过文件夹
        if not self.audio_files:
            # 1. 扫描文件夹
            self.scan_folder()
        
        if not self.audio_files:
            print("[ERROR] 未找到音频文件")
            return
        
        # 2. 转写第一个音频文件
        audio_path = self.audio_files[0]
        text, result_json = self.transcribe_audio(audio_path)
        
        if not result_json:
            print("[ERROR] 音频转写失败")
            return
        
        # 3. 转换为SRT格式
        srt_path = os.path.splitext(audio_path)[0] + ".srt"
        self.json_to_srt(result_json, srt_path)
        
        # 4. 插入图片链接
        if self.image_timestamps:
            srt_with_images = self.insert_image_links(srt_path)
        else:
            srt_with_images = srt_path
            print("[ERROR] 未找到图片文件，跳过图片链接插入")
        
        # 5. 生成摘要
        self.generate_summary_with_images(srt_with_images, understand_images)
        
        print("=" * 50)
        print("会议转写处理完成")
        print("=" * 50)

def main():
    parser = argparse.ArgumentParser(description='会议音频转写和图片理解工具')
    parser.add_argument('folder', help='包含音频和图片的文件夹路径')
        # 从配置文件获取默认值
    from util.config_manager import get_xunfei_config
    xunfei_config = get_xunfei_config()
    default_appid = xunfei_config.get('appid', '')
    default_secret = xunfei_config.get('secret', '')
    
    parser.add_argument('--appid', default=default_appid, help='讯飞API AppID')
    parser.add_argument('--apisecret', default=default_secret, help='讯飞API Secret')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.folder):
        print(f"[ERROR] 文件夹不存在: {args.folder}")
        return
    
    # 创建转写器实例
    transcriber = MeetingTranscriber(args.folder, args.appid, args.apisecret)
    
    # 扫描文件夹
    transcriber.scan_folder()
    
    # 让用户选择图片处理方式
    print("\n" + "="*50)
    print("请选择图片处理方式：")
    print("1. 理解图片内容 - 使用多模态模型分析图片并生成摘要")
    print("2. 直接引用图片 - 仅保留图片链接引用，不分析图片内容")
    print("="*50)
    
    while True:
        choice = input("请输入选择 (1 或 2): ").strip()
        if choice == "1":
            understand_images = True
            print("[INFO] 已选择：理解图片内容")
            break
        elif choice == "2":
            understand_images = False
            print("[INFO] 已选择：直接引用图片")
            break
        else:
            print("[ERROR] 无效选择，请输入 1 或 2")
    
    # 处理会议
    transcriber.process_meeting(understand_images)

if __name__ == "__main__":
    main() 

