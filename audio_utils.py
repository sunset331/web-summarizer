import requests
import os
import time
import hashlib
import hmac
import base64
import json
from pydub import AudioSegment
import urllib.parse
from typing import List, Dict

# ====== 通用工具函数 ======

def download_audio(audio_url, save_dir, filename=None):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    if not filename:
        filename = audio_url.split('/')[-1].split('?')[0]
    save_path = os.path.join(save_dir, filename)
    resp = requests.get(audio_url, stream=True)
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
        return save_path

def convert_to_wav(input_path, output_path):
    """
    将音频文件转换为讯飞API要求的格式：
    - 采样率：16kHz
    - 位深度：16bit
    - 声道：单声道
    - 格式：WAV
    - 编码：PCM
    """
    try:
        audio = AudioSegment.from_file(input_path)
        
        # 转换为讯飞API要求的格式
        audio = audio.set_frame_rate(16000)  # 16kHz采样率
        audio = audio.set_sample_width(2)    # 16bit位深度
        audio = audio.set_channels(1)        # 单声道
        
        # 导出为WAV格式，确保PCM编码
        audio.export(output_path, format="wav", parameters=["-ac", "1", "-ar", "16000", "-sample_fmt", "s16"])
        
        print(f"[INFO] 音频格式转换完成: {output_path}")
        print(f"[INFO] 采样率: 16kHz, 位深度: 16bit, 声道: 单声道")
        
        return output_path
    except Exception as e:
        print(f"[ERROR] 音频格式转换失败: {e}")
        raise

def convert_to_xunfei_format(input_path, output_path):
    """
    专门为讯飞API转换音频格式
    
    讯飞录音文件转写API要求：
    - 音频格式：WAV
    - 采样率：16kHz
    - 位深度：16bit
    - 声道：单声道
    - 编码：PCM
    - 文件大小：不超过500MB
    - 时长：不超过5小时
    """
    try:
        print(f"[INFO] 开始转换音频格式为讯飞API要求...")
        
        # 使用pydub加载音频
        audio = AudioSegment.from_file(input_path)
        
        # 获取原始音频信息
        original_frame_rate = audio.frame_rate
        original_channels = audio.channels
        original_sample_width = audio.sample_width
        
        print(f"[INFO] 原始音频信息:")
        print(f"[INFO] 采样率: {original_frame_rate}Hz")
        print(f"[INFO] 声道数: {original_channels}")
        print(f"[INFO] 位深度: {original_sample_width * 8}bit")
        
        # 转换为讯飞API要求的格式
        audio = audio.set_frame_rate(16000)  # 16kHz采样率
        audio = audio.set_channels(1)        # 单声道
        audio = audio.set_sample_width(2)    # 16bit位深度
        
        # 导出为WAV格式，使用PCM编码
        audio.export(
            output_path, 
            format="wav",
            parameters=[
                "-ac", "1",           # 单声道
                "-ar", "16000",       # 16kHz采样率
                "-sample_fmt", "s16"  # 16bit PCM编码
            ]
        )
        
        print(f"[INFO] 音频格式转换完成")
        return output_path
            
    except Exception as e:
        print(f"[ERROR] 音频格式转换失败: {e}")
        raise

def summarize_text(text):
    try:
        from .generate_summary import generate_summary
        return generate_summary(text, api_key="", model_name="")
    except ImportError:
        return "[ERROR] 摘要功能未实现或依赖缺失" 

lfasr_host_long = 'https://raasr.xfyun.cn/v2/api'
api_upload_long = '/upload'
api_get_result_long = '/getResult'

class XunfeiLongASR:
    def __init__(self, appid, secret_key, upload_file_path, role_type=2, hot_word=None):
        self.appid = appid
        self.secret_key = secret_key
        self.upload_file_path = upload_file_path
        self.ts = str(int(time.time()))
        self.signa = self.get_signa()
        self.role_type = role_type
        self.hot_word = hot_word

    def get_signa(self):
        appid = self.appid
        secret_key = self.secret_key
        m2 = hashlib.md5()
        m2.update((appid + self.ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        signa = hmac.new(secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        signa = str(signa, 'utf-8')
        return signa

    def upload(self):
        print("[INFO] [LongASR] 上传部分：")
        upload_file_path = self.upload_file_path
        file_len = os.path.getsize(upload_file_path)
        file_name = os.path.basename(upload_file_path)
        
        # 计算音频实际时长
        try:
            audio = AudioSegment.from_file(upload_file_path)
            duration_seconds = len(audio) / 1000.0
            duration_str = str(int(duration_seconds))
            print(f"[INFO] 计算音频时长: {duration_seconds:.1f}秒")
        except Exception as e:
            print(f"[INFO] 无法计算音频时长，使用默认值: {e}")
            duration_str = '200'  # 默认值
        
        param_dict = {
            'appId': self.appid,
            'signa': self.signa,
            'ts': self.ts,
            'fileSize': file_len,
            'fileName': file_name,
            'duration': duration_str,
            'roleType': self.role_type
        }
        if self.hot_word:
            param_dict['hotWord'] = self.hot_word
        print("[INFO] upload参数：", param_dict)
        data = open(upload_file_path, 'rb').read(file_len)
        response = requests.post(url=lfasr_host_long + api_upload_long + "?" + urllib.parse.urlencode(param_dict),
                                 headers={"Content-type": "application/json"}, data=data)
        print("[INFO] upload_url:", response.request.url)
        result = json.loads(response.text)
        print("[INFO] upload resp:", result)
        return result

    def get_result(self):
        uploadresp = self.upload()
        if 'content' not in uploadresp or not uploadresp['content'] or 'orderId' not in uploadresp['content']:
            raise Exception(f"上传失败: {uploadresp}")
        orderId = uploadresp['content']['orderId']
        param_dict = {
            'appId': self.appid,
            'signa': self.signa,
            'ts': self.ts,
            'orderId': orderId,
            'resultType': 'transfer',
        }
        print("\n[INFO] [LongASR] 查询部分：")
        print("[INFO] get result参数：", param_dict)
        status = 3
        result = None
        while status == 3:
            response = requests.post(url=lfasr_host_long + api_get_result_long + "?" + urllib.parse.urlencode(param_dict),
                                     headers={"Content-type": "application/json"})
            result = json.loads(response.text)
            print("[INFO] get_result resp:", result)
            if result and 'content' in result and result['content'] and 'orderInfo' in result['content'] and result['content']['orderInfo']:
                status = result['content']['orderInfo']['status']
                print("[INFO] status=", status)
                if status == 4:
                    break
            else:
                print("[ERROR] 查询结果格式异常", result)
                break
            time.sleep(10) 
        return result


def xunfei_asr_long(file_path, appid, secret_key, role_type=2, hot_word=None):
    """
    讯飞新版录音文件转写API一站式调用，返回(转写文本, 原始json)。
    role_type=1 开启角色分离，0为关闭。
    hot_word: 热词, 格式 "热词1|热词2"
    """
    asr = XunfeiLongASR(appid, secret_key, file_path, role_type=role_type, hot_word=hot_word)
    result_json = asr.get_result()
    
    # 检查转写结果的时间范围
    print("[INFO] 检查转写结果时间范围...")
    if isinstance(result_json, dict) and 'content' in result_json:
        content = result_json['content']
        if 'orderResult' in content:
            order_result = content['orderResult']
            if isinstance(order_result, dict) and 'transferList' in order_result:
                transfer_list = order_result['transferList']
                if transfer_list:
                    # 提取所有时间戳
                    all_times = []
                    for seg in transfer_list:
                        if 'bg' in seg:
                            all_times.append(seg['bg'])
                        if 'ed' in seg:
                            all_times.append(seg['ed'])
                    
                    if all_times:
                        max_time = max(all_times) / 1000.0  # 转换为秒
                        min_time = min(all_times) / 1000.0
                        print(f"[INFO] 转写结果时间范围: {min_time:.1f}s - {max_time:.1f}s ({max_time/60:.1f}分钟)")
    
    # 提取文本内容
    try:
        if not isinstance(result_json, dict):
            content = {}
        else:
            content = result_json.get('content', {})
        
        # 先预处理orderResult
        result_json = preprocess_order_result(result_json)
        content = result_json.get('content', {})
        order_result = content.get('orderResult', {})
        
        # 优先尝试lattice结构（讯飞新版API格式）
        if isinstance(order_result, dict) and 'lattice' in order_result:
            lattice = order_result['lattice']
            text_parts = []
            for seg in lattice:
                if isinstance(seg, dict) and 'json_1best' in seg:
                    json_1best = seg['json_1best']
                    if isinstance(json_1best, dict) and 'st' in json_1best:
                        st = json_1best['st']
                        for rt in st.get('rt', []):
                            for ws in rt.get('ws', []):
                                for cw in ws.get('cw', []):
                                    text_parts.append(cw.get('w', ''))
            text = ''.join(text_parts)
            if not text.strip():
                raise Exception('lattice结构解析结果为空')
        
        # 如果lattice结构失败，尝试transferList结构
        elif isinstance(order_result, dict) and 'transferList' in order_result:
            transfer_list = order_result['transferList']
            if not transfer_list:
                raise Exception('transferList为空')
            text = '\n'.join([seg['text'] for seg in transfer_list if 'text' in seg])
        
        else:
            raise Exception('未找到有效的转写结果结构')
            
    except Exception as e:
        print(f"[ERROR] 标准结构解析失败，自动尝试兼容提取: {e}")
        # 兼容极速版API结构
        try:
            # 递归提取json_1best文本
            def extract_json_1best(obj):
                if not isinstance(obj, dict):
                    return ""
                if "json_1best" in obj and isinstance(obj["json_1best"], dict):
                    st = obj["json_1best"].get("st", {})
                    rt_list = st.get("rt", [])
                    para = []
                    for rt in rt_list:
                        ws_list = rt.get("ws", [])
                        for ws in ws_list:
                            cw_list = ws.get("cw", [])
                            for cw in cw_list:
                                w = cw.get("w", "")
                                para.append(w)
                    return "".join(para)
                # 递归
                for v in obj.values():
                    if isinstance(v, dict):
                        res = extract_json_1best(v)
                        if res:
                            return res
                    elif isinstance(v, list):
                        for item in v:
                            res = extract_json_1best(item)
                            if res:
                                return res
                return ""
            text = extract_json_1best(result_json)
            if not text:
                text = str(result_json)
        except Exception as e2:
            print(f"[ERROR] 极速版结构解析失败: {e2}")
            text = str(result_json)
    return text, result_json


def preprocess_order_result(result_json):
    """
    1. 如果 result_json['content']['orderResult'] 是字符串且内容像json，则先解析为对象
    2. 如果 orderResult.lattice[*].json_1best 是字符串且内容像json，也转为对象
    """
    import json
    content = result_json.get('content', {})
    order_result = content.get('orderResult')
    # 1. 先处理 orderResult 本身
    if isinstance(order_result, str):
        s = order_result.strip()
        if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
            try:
                loaded = json.loads(s)
                content['orderResult'] = loaded
                order_result = loaded
                result_json['content'] = content
            except Exception:
                pass
    # 2. 再处理 lattice[*].json_1best
    def process_lattice_json_1best(order_result):
        if isinstance(order_result, dict) and 'lattice' in order_result and isinstance(order_result['lattice'], list):
            for item in order_result['lattice']:
                if isinstance(item, dict) and 'json_1best' in item and isinstance(item['json_1best'], str):
                    s = item['json_1best'].strip()
                    if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                        try:
                            item['json_1best'] = json.loads(s)
                        except Exception:
                            pass
    process_lattice_json_1best(content.get('orderResult'))
    return result_json


def extract_all_text_from_json(data):
    """
    从讯飞ASR的JSON结果中提取带角色标签的文本。
    优先使用rl字段作为角色编号。
    """
    import json

    def _recursive_extract(obj):
        texts = []
        if isinstance(obj, str):
            s = obj.strip()
            if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                try:
                    obj = json.loads(s)
                except Exception:
                    return []
            else:
                return []

        if isinstance(obj, list):
            for item in obj:
                texts.extend(_recursive_extract(item))
            return texts

        if not isinstance(obj, dict):
            return []

        processed = False
        # 优先处理 lattice -> json_1best 结构
        if 'lattice' in obj and isinstance(obj['lattice'], list):
            print(f"[INFO] 找到lattice结构，长度: {len(obj['lattice'])}")
            for i, seg in enumerate(obj['lattice']):
                try:
                    if isinstance(seg, dict) and 'json_1best' in seg and isinstance(seg['json_1best'], dict):
                        st = seg['json_1best'].get('st', {})
                        # 角色ID在st层级，不是rt层级
                        role_id = st.get('rl', None)
                        print(f"[INFO] 找到rl字段: {role_id}")
                        sentence = []
                        for rt in st.get('rt', []):
                            if isinstance(rt, dict):
                                for ws in rt.get('ws', []):
                                    if isinstance(ws, dict):
                                        for cw in ws.get('cw', []):
                                            if isinstance(cw, dict):
                                                sentence.append(cw.get('w', ''))
                        if sentence:
                            display_role = f"角色-{role_id}" if role_id is not None else "未知角色"
                            texts.append(f"{display_role}: {''.join(sentence)}")
                except Exception as e:
                    print(f"[ERROR] 处理lattice第{i}项时出错: {e}")
                    continue
            processed = True

        # 其次处理 transferList 结构
        if 'transferList' in obj and isinstance(obj['transferList'], list):
            print(f"[INFO] 找到transferList结构，长度: {len(obj['transferList'])}")
            for i, seg in enumerate(obj['transferList']):
                try:
                    if isinstance(seg, dict) and 'text' in seg:
                        role_id = seg.get('rl', None)
                        print(f"[INFO] transferList中找到rl字段: {role_id}")
                        display_role = f"角色-{role_id}" if role_id is not None else "未知角色"
                        texts.append(f"{display_role}: {seg['text']}")
                except Exception as e:
                    print(f"[ERROR] 处理transferList第{i}项时出错: {e}")
                    continue
            processed = True

        # 如果没有找到特定的高层结构，再进行通用递归
        if not processed:
            for v in obj.values():
                texts.extend(_recursive_extract(v))

        return texts

    return _recursive_extract(data)


def summarize_text_blocks(text, block_size=8000):
    """
    将长文本自动分块摘要，合并结果。每块默认8000字。
    """
    blocks = [text[i:i+block_size] for i in range(0, len(text), block_size)]
    summaries = []
    for idx, block in enumerate(blocks):
        try:
            from .generate_summary import generate_summary
            summary = generate_summary(block, api_key="", model_name="")
            summaries.append(f"### 分块 {idx+1} 摘要\n" + summary)
        except Exception as e:
            summaries.append(f"### 分块 {idx+1} 摘要生成失败: {e}")
    return '\n\n'.join(summaries)

def transcribe_audio_from_video(video_path: str, appid: str = None, secret_key: str = None) -> List[Dict]:
    """
    从视频文件中提取音频并进行转写
    
    Args:
        video_path: 视频文件路径
        appid: 讯飞API的appid
        secret_key: 讯飞API的secret_key
        
    Returns:
        音频转写结果列表
    """
    import os
    import tempfile
    import time
    
    # 导入用量统计器
    try:
        from util.llm_usage_tracker import record_xunfei_usage
        use_tracking = True
    except ImportError:
        use_tracking = False
    
    start_time = time.time()
    success = False
    error_message = ""
    # 获取API配置
    # 从配置文件获取讯飞API配置
    from util.config_manager import get_xunfei_config
    xunfei_config = get_xunfei_config()
    appid = xunfei_config.get('appid')
    secret_key = xunfei_config.get('secret')
    
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        
        # 使用ffmpeg提取音频（如果可用）
        wav_path = os.path.join(temp_dir, "audio_16k.wav")
        
        try:
            import subprocess
            # 使用ffmpeg提取音频并转换为16kHz/16bit/单声道
            cmd = [
                'ffmpeg', '-i', video_path,
                '-ac', '1',           # 单声道
                '-ar', '16000',       # 16kHz采样率
                '-acodec', 'pcm_s16le', # 16bit PCM编码
                '-y',                 # 覆盖输出文件
                wav_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[INFO] 使用ffmpeg提取音频成功")
            else:
                raise Exception(f"ffmpeg提取失败: {result.stderr}")
                
        except (ImportError, FileNotFoundError, Exception) as e:
            print(f"[ERROR] ffmpeg不可用: {e}")
            print("[INFO] 跳过音频转写，继续处理PPT内容...")
            return []
        
        print(f"[INFO] 音频提取完成，格式: 16kHz/16bit/单声道/PCM")
        
        # 使用讯飞API进行转写
        print("开始音频转写...")
        print("正在调用讯飞语音识别API...")
        text, result_json = xunfei_asr_long(wav_path, appid, secret_key, role_type=2)
        
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir)
        
        if text and result_json:
            print("音频转写完成！")
            # 使用preprocess_order_result预处理结果
            result_json = preprocess_order_result(result_json)
            
            # 构造返回格式
            segments = []
            if isinstance(result_json, dict) and 'content' in result_json:
                content = result_json['content']
                if 'orderResult' in content:
                    order_result = content['orderResult']
                    
                    # 处理lattice结构（讯飞新版API格式）
                    if isinstance(order_result, dict) and 'lattice' in order_result:
                        lattice = order_result['lattice']
                        for seg in lattice:
                            try:
                                if isinstance(seg, dict) and 'json_1best' in seg:
                                    json_1best = seg['json_1best']
                                    if isinstance(json_1best, dict) and 'st' in json_1best:
                                        st = json_1best['st']
                                        # 提取文本
                                        text_parts = []
                                        for rt in st.get('rt', []):
                                            if isinstance(rt, dict):
                                                for ws in rt.get('ws', []):
                                                    if isinstance(ws, dict):
                                                        for cw in ws.get('cw', []):
                                                            if isinstance(cw, dict):
                                                                text_parts.append(cw.get('w', ''))
                                        segment_text = ''.join(text_parts)
                                        
                                        if segment_text.strip():
                                            segments.append({
                                                'start_time': int(st.get('bg', 0)) / 1000.0,  # 转换为秒
                                                'end_time': int(st.get('ed', 0)) / 1000.0,    # 转换为秒
                                                'text': segment_text,
                                                'confidence': float(st.get('sc', 0.0))
                                            })
                            except Exception as e:
                                print(f"[ERROR] 处理lattice片段时出错: {e}")
                                continue
                    
                    # 处理transferList结构（兼容旧版格式）
                    elif isinstance(order_result, dict) and 'transferList' in order_result:
                        transfer_list = order_result['transferList']
                        for seg in transfer_list:
                            try:
                                if isinstance(seg, dict) and 'text' in seg:
                                    segments.append({
                                        'start_time': seg.get('bg', 0) / 1000.0,  # 转换为秒
                                        'end_time': seg.get('ed', 0) / 1000.0,    # 转换为秒
                                        'text': seg['text'],
                                        'confidence': seg.get('confidence', 0.0)
                                    })
                            except Exception as e:
                                print(f"[ERROR] 处理transferList片段时出错: {e}")
                                continue
            
            if segments:
                success = True
                output_chars = len(text) if text else 0
                
                # 获取音频时长和估算输入token数
                try:
                    result = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', wav_path], capture_output=True, text=True)
                    duration = float(result.stdout.strip()) if result.stdout.strip() else 0
                    # 讯飞ASR通常按音频时长计费，这里按实际转写字符数计算
                    actual_chars = len(text) if text else 0
                    estimated_chars = actual_chars  # 使用实际转写结果长度
                except:
                    duration = 0
                    actual_chars = len(text) if text else 0
                    estimated_chars = actual_chars
                
                # 记录用量统计
                if use_tracking:
                    api_duration = time.time() - start_time
                    record_xunfei_usage(
                        input_tokens=estimated_chars,
                        output_tokens=output_chars,
                        duration=api_duration,
                        audio_duration=duration if 'duration' in locals() else 0,
                        success=True,
                        metadata={
                            'video_path': video_path,
                            'segments_count': len(segments),
                            'token_source': 'actual_transcription'
                        }
                    )
                
                return segments
            else:
                # 如果没有结构化数据，返回简单格式
                success = True
                output_chars = len(text) if text else 0
                
                # 记录用量统计
                if use_tracking:
                    api_duration = time.time() - start_time
                    record_xunfei_usage(
                        input_tokens=len(text) if text else 0,
                        output_tokens=output_chars,
                        duration=api_duration,
                        audio_duration=duration if 'duration' in locals() else 0,
                        success=True,
                        metadata={
                            'video_path': video_path,
                            'segments_count': 1
                        }
                    )
                
                return [{'text': text, 'start_time': 0, 'end_time': 0, 'confidence': 0.0}]
        else:
            error_message = "音频转写失败或返回结果为空"
            print(error_message)
            
            # 记录失败统计
            if use_tracking:
                api_duration = time.time() - start_time
                record_xunfei_usage(
                    input_tokens=0,
                    output_tokens=0,
                    duration=api_duration,
                    audio_duration=duration if 'duration' in locals() else 0,
                    success=False,
                    error_message=error_message
                )
            
            return []
            
    except Exception as e:
        print(f"[ERROR] 视频音频转写失败: {e}")
        return [] 