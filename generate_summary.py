from openai import OpenAI
from util.chunk_content import chunk_content
from typing import Dict

def generate_summary(text: str, api_key: str = "", model_name: str = "") -> str:
    """
    使用火山引擎豆包大模型生成摘要。
    为每一行内容添加ID，方便用户定位到原文具体行。
    """
    # 从配置文件获取豆包API配置
    from util.config_manager import get_doubao_config
    doubao_config = get_doubao_config()
    api_key = api_key or doubao_config.get('api_key')
    base_url = doubao_config.get('base_url')
    model = model_name or doubao_config.get('model')
    
    # 为文本的每一行添加ID
    text_with_ids = _add_paragraph_ids(text)
    
    chunks = chunk_content(text_with_ids)
    summaries = []
    print(f"检测到 {len(chunks)} 个文本块需要处理")
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    for i, chunk in enumerate(chunks):
        print(f"处理分块 {i+1}/{len(chunks)} (约 {len(chunk)} 字符)")
        
        # 增加重试机制
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            try:
                print(f"  尝试 {attempt + 1}/{max_retries}...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的摘要生成专家。请生成结构化、简洁、包含要点的Markdown格式摘要。\n\n重要要求：\n1. 保留关键数据和专业术语\n2. 使用中文输出结果\n3. 每个摘要要点都要引用原文行ID，格式为：[行ID] 或 [行ID1-行ID2]\n4. 如果某个要点涉及多行内容，请用连字符连接，如：[P001-P003]\n5. 行ID引用要准确，帮助用户快速定位到原文具体行"},
                        {"role": "user", "content": f"请为以下内容生成详细摘要，使用Markdown格式，包含主要观点、关键数据和结论。代码部分全部保留并高亮，图片链接全部保留引用。\n\n重要：每个摘要要点都要引用对应的行ID，格式为：[行ID]：\n\n{chunk}"}
                    ],
                    temperature=0.3,
                    max_tokens=20000,
                    timeout=120  # 增加超时时间到120秒
                )
                content = response.choices[0].message.content
                summary = content.strip() if content else ""
                summaries.append(summary)
                print(f"分块 {i+1} 摘要生成成功")
                success = True
                break
                
            except Exception as e:
                print(f"  尝试 {attempt + 1}/{max_retries} 失败: {str(e)}")
                if attempt < max_retries - 1:
                    print("  等待5秒后重试...")
                    import time
                    time.sleep(5)
                else:
                    print(f"[ERROR] 分块 {i+1} 所有重试都失败")
                    # 生成备用摘要
                    fallback_summary = _generate_fallback_summary(chunk, i+1)
                    summaries.append(fallback_summary)
    
    if not summaries:
        return "摘要生成失败,请检查API密钥或网络连接"
    if len(summaries) == 1:
        return summaries[0]
    
    combined_summary = "\n\n".join(summaries)
    print("整合分段摘要...")
    
    # 为摘要整合也增加重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  尝试整合摘要 {attempt + 1}/{max_retries}...")
            response = client.chat.completions.create(
                model=model,
                messages=[
                                            {"role": "system", "content": "你是一个专业编辑,请将以下分段摘要整合成一份连贯的完整摘要,保持Markdown格式,确保逻辑流畅。\n\n重要：保持所有行ID引用，格式为：[行ID] 或 [行ID1-行ID2]，这些引用对用户定位原文很重要。"},
                                            {"role": "user", "content": f"请整合以下分段摘要，代码部分全部保留并高亮，图片链接全部保留引用。保持所有行ID引用：\n\n{combined_summary}"}
                ],
                temperature=0.2,
                max_tokens=2500,
                timeout=120  # 增加超时时间到120秒
            )
            content = response.choices[0].message.content
            return content.strip() if content else combined_summary
            
        except Exception as e:
            print(f"  尝试整合摘要 {attempt + 1}/{max_retries} 失败: {str(e)}")
            if attempt < max_retries - 1:
                print("  等待5秒后重试...")
                import time
                time.sleep(5)
            else:
                print(f"[ERROR] 摘要整合失败: {str(e)}")
                return combined_summary

def generate_audio_summary(text: str, api_key: str = "", model_name: str = "") -> str:
    """
    专门用于音频转文字内容的摘要生成。
    先根据上下文修正语音识别错误，再进行摘要。
    每个摘要分点都会标注对应的时间戳范围。
    """
    # 从配置文件获取豆包API配置
    from util.config_manager import get_doubao_config
    doubao_config = get_doubao_config()
    api_key = api_key or doubao_config.get('api_key')
    base_url = doubao_config.get('base_url')
    model = doubao_config.get('model')

    # 解析音频转文字内容，提取时间戳信息
    timestamp_info = _extract_timestamp_info(text)

    chunks = chunk_content(text)
    summaries = []
    print(f"检测到 {len(chunks)} 个音频文本块需要处理")
    client = OpenAI(api_key=api_key, base_url=base_url)

    for i, chunk in enumerate(chunks):
        print(f"处理音频分块 {i+1}/{len(chunks)} (约 {len(chunk)} 字符)")

        # 为当前分块添加时间戳信息
        chunk_with_timestamp = _add_timestamp_to_chunk(chunk, timestamp_info, i, len(chunks))

        # 从配置文件获取重试次数
        max_retries = doubao_config.get('max_retries', 3)
        success = False

        for attempt in range(max_retries):
            try:
                print(f"  尝试 {attempt + 1}/{max_retries}...")

                # 一次调用：同时修正语音识别错误并生成摘要
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的音频内容处理专家。请按以下步骤处理语音转文字内容：\n\n1. 修正语音识别错误：根据上下文理解对话内容，修正明显的识别错误，保持原意不变\n2. 生成结构化摘要：为修正后的内容生成Markdown格式摘要\n\n注意事项：\n- 保留角色标签（如'角色-1:'）\n- 只修正明显的识别错误\n- 重点关注主要讨论话题、关键观点、不同角色的重要发言\n- 使用Markdown格式输出摘要\n- 文本中每行末尾已包含时间戳格式 [时间范围：开始时间-结束时间]，请直接使用这些时间戳\n- 每个摘要分点都要标注对应的时间范围，格式为：**时间戳：XX分XX秒-XX分XX秒**\n- 时间戳标注必须放在每个摘要点的开头，格式要统一"},
                        {"role": "user", "content": f"请处理以下音频转文字内容，先修正识别错误，再生成摘要。注意：文本中每行末尾已包含时间戳，请直接使用这些时间戳，每个摘要分点都要标注对应的时间范围，格式为：**时间戳：XX分XX秒-XX分XX秒**\n\n{chunk_with_timestamp}"}
                    ],
                    temperature=doubao_config.get('temperature', 0.2),
                    max_tokens=doubao_config.get('max_tokens', 20000),
                    timeout=doubao_config.get('timeout', 120)
                )
                content = response.choices[0].message.content
                summary = content.strip() if content else ""
                summaries.append(summary)
                print(f"音频分块 {i+1} 修正和摘要生成成功")
                success = True
                break

            except Exception as e:
                error_msg = str(e)
                print(f"  尝试 {attempt + 1} 失败: {error_msg}")

                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    if attempt < max_retries - 1:
                        print(f"  超时错误，等待后重试...")
                        import time
                        time.sleep(5)  # 等待5秒后重试
                        continue
                    else:
                        print(f"  所有重试都超时，使用备用方案")
                else:
                    print(f"  其他错误，不再重试")
                    break

        if not success:
            # 生成备用摘要
            fallback_summary = _generate_fallback_summary(chunk_with_timestamp, i+1)
            summaries.append(fallback_summary)
            print(f"音频分块 {i+1} 使用备用摘要")

    if not summaries:
        return "音频摘要生成失败,请检查API密钥或网络连接"
    if len(summaries) == 1:
        return summaries[0]

    combined_summary = "\n\n".join(summaries)
    print("整合音频分段摘要...")

    # 整合摘要也增加重试机制
    max_retries = doubao_config.get('max_retries', 3)
    for attempt in range(max_retries):
        try:
            print(f"整合摘要尝试 {attempt + 1}/{max_retries}...")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个专业编辑,请将以下音频分段摘要整合成一份连贯的完整摘要,保持Markdown格式,突出对话的核心内容和不同角色的观点。确保每个摘要分点的时间戳标注清晰准确。注意：时间戳信息应该从原始文本中提取，保持准确性。"},
                    {"role": "user", "content": f"请整合以下音频分段摘要，保持对话的完整性和逻辑流畅，确保时间戳标注准确。时间戳信息应该与原始音频内容的时间范围一致：\n\n{combined_summary}"}
                ],
                temperature=0.2,
                max_tokens=2500,
                timeout=90
            )
            content = response.choices[0].message.content
            return content.strip() if content else combined_summary
        except Exception as e:
            error_msg = str(e)
            print(f"整合摘要尝试 {attempt + 1} 失败: {error_msg}")
            if attempt < max_retries - 1:
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    print(f"整合摘要超时，等待后重试...")
                    import time
                    time.sleep(5)
                    continue
            break

    print(f"整合摘要失败，返回分段摘要")
    return combined_summary

def _extract_timestamp_info(text: str) -> Dict:
    """
    从音频转文字内容中提取时间戳信息
    支持两种格式：
    1. 已包含时间戳的文本格式：每行末尾有 [时间范围：开始时间-结束时间]
    2. JSON格式：包含bg(开始时间)和ed(结束时间)字段，单位为毫秒（备用方案）

    Args:
        text: 音频转文字内容

    Returns:
        包含时间戳信息的字典
    """
    timestamp_info = {
        'total_duration': 0,
        'segments': []
    }

    try:
        import re
        
        # 首先检查文本是否已经包含时间戳格式 [时间范围：开始时间-结束时间]
        timestamp_pattern = r'\[时间范围：([^-]+)-([^\]]+)\]'
        timestamp_matches = re.findall(timestamp_pattern, text)
        
        if timestamp_matches:
            print(f"[INFO] 检测到文本已包含时间戳格式，共 {len(timestamp_matches)} 个时间段")
            
            # 解析已有的时间戳
            all_times = []
            for start_str, end_str in timestamp_matches:
                try:
                    # 解析时间格式：X分Y秒 或 X.Y秒
                    start_seconds = _parse_time_string(start_str.strip())
                    end_seconds = _parse_time_string(end_str.strip())
                    
                    if start_seconds >= 0 and end_seconds >= 0:
                        timestamp_info['segments'].append({
                            'start': start_seconds,
                            'end': end_seconds,
                            'text': ''  # 文本内容在原始文本中
                        })
                        all_times.extend([start_seconds, end_seconds])
                        
                except (ValueError, TypeError) as e:
                    print(f"[WARNING] 解析时间戳失败: {start_str}-{end_str}, 错误: {e}")
                    continue
            
            if all_times:
                timestamp_info['total_duration'] = max(all_times)
                print(f"[INFO] 从文本时间戳解析到音频总时长: {timestamp_info['total_duration']:.1f}秒 ({timestamp_info['total_duration']/60:.1f}分钟)")
                print(f"[INFO] 检测到 {len(timestamp_info['segments'])} 个时间段")
                return timestamp_info
        
        # 如果没有检测到时间戳格式，尝试JSON解析（备用方案）
        try:
            import json
            data = json.loads(text)
            
            # 检查是否包含时间戳信息
            if isinstance(data, dict) and 'data' in data:
                # 常见的API返回格式：{"data": [{"bg": "1000", "ed": "5000", "text": "..."}]}
                segments = data['data']
                if isinstance(segments, list) and segments:
                    all_times = []
                    for segment in segments:
                        if isinstance(segment, dict) and 'bg' in segment and 'ed' in segment:
                            try:
                                bg_ms = int(segment['bg'])  # 开始时间（毫秒）
                                ed_ms = int(segment['ed'])  # 结束时间（毫秒）
                                
                                # 转换为秒
                                bg_seconds = bg_ms / 1000
                                ed_seconds = ed_ms / 1000
                                
                                # 添加到时间段列表
                                timestamp_info['segments'].append({
                                    'start': bg_seconds,
                                    'end': ed_seconds,
                                    'text': segment.get('text', '')
                                })
                                
                                all_times.extend([bg_seconds, ed_seconds])
                                
                            except (ValueError, TypeError):
                                continue
                    
                    if all_times:
                        timestamp_info['total_duration'] = max(all_times)
                        print(f"[INFO] 从JSON解析到音频总时长: {timestamp_info['total_duration']:.1f}秒 ({timestamp_info['total_duration']/60:.1f}分钟)")
                        print(f"[INFO] 检测到 {len(timestamp_info['segments'])} 个时间段")
                        return timestamp_info
                        
            elif isinstance(data, list):
                # 直接是列表格式：[{"bg": "1000", "ed": "5000", "text": "..."}]
                segments = data
                if segments:
                    all_times = []
                    for segment in segments:
                        if isinstance(segment, dict) and 'bg' in segment and 'ed' in segment:
                            try:
                                bg_ms = int(segment['bg'])
                                ed_ms = int(segment['ed'])
                                
                                bg_seconds = bg_ms / 1000
                                ed_seconds = bg_ms / 1000
                                
                                timestamp_info['segments'].append({
                                    'start': bg_seconds,
                                    'end': ed_seconds,
                                    'text': segment.get('text', '')
                                })
                                
                                all_times.extend([bg_seconds, ed_seconds])
                                
                            except (ValueError, TypeError):
                                continue
                    
                    if all_times:
                        timestamp_info['total_duration'] = max(all_times)
                        print(f"[INFO] 从JSON列表解析到音频总时长: {timestamp_info['total_duration']:.1f}秒 ({timestamp_info['total_duration']/60:.1f}分钟)")
                        print(f"[INFO] 检测到 {len(timestamp_info['segments'])} 个时间段")
                        return timestamp_info
            
            # 检查讯飞语音识别格式：包含bg(句子开始时间)和ed(句子结束时间)字段
            if isinstance(data, dict) and 'content' in data and 'orderResult' in data['content']:
                order_result = data['content']['orderResult']
                if 'lattice' in order_result:
                    lattice = order_result['lattice']
                    if isinstance(lattice, list) and lattice:
                        all_times = []
                        
                        # 遍历所有识别结果
                        for lattice_item in lattice:
                            if 'json_1best' in lattice_item:
                                json_1best = lattice_item['json_1best']
                                if 'st' in json_1best and 'rt' in json_1best['st']:
                                    st = json_1best['st']
                                    rt = st['rt']
                                    
                                    # 检查句子级别的时间戳：bg和ed在st级别
                                    if 'bg' in st and 'ed' in st and isinstance(rt, list):
                                        try:
                                            bg = int(st['bg'])  # 句子开始时间（毫秒）
                                            ed = int(st['ed'])  # 句子结束时间（毫秒）
                                            
                                            # 转换为秒
                                            start_seconds = bg / 1000.0
                                            end_seconds = ed / 1000.0
                                            
                                            # 提取整个句子的文本内容
                                            text_content = ""
                                            for rt_item in rt:
                                                if 'ws' in rt_item and isinstance(rt_item['ws'], list):
                                                    for ws_item in rt_item['ws']:
                                                        if 'cw' in ws_item and isinstance(ws_item['cw'], list):
                                                            text_content += "".join([cw_item.get('w', '') for cw_item in ws_item['cw']])
                                            
                                            # 添加到时间段列表
                                            timestamp_info['segments'].append({
                                                'start': start_seconds,
                                                'end': end_seconds,
                                                'text': text_content
                                            })
                                            
                                            all_times.extend([start_seconds, end_seconds])
                                            
                                        except (ValueError, TypeError):
                                            continue
                        
                        if all_times:
                            timestamp_info['total_duration'] = max(all_times)
                            print(f"[INFO] 从讯飞语音识别结果解析到音频总时长: {timestamp_info['total_duration']:.1f}秒 ({timestamp_info['total_duration']/60:.1f}分钟)")
                            print(f"[INFO] 检测到 {len(timestamp_info['segments'])} 个时间段")
                            return timestamp_info
                        
        except (json.JSONDecodeError, KeyError, TypeError):
            # JSON解析失败，继续使用文本模式
            pass
        
        # 备用方案：从文本中提取时间信息
        print(f"[INFO] JSON解析失败，使用文本模式提取时间信息")
        
        # 查找时间戳模式：如 "12.5s", "1:23", "1分30秒" 等
        time_patterns = [
            r'(\d+\.?\d*)\s*秒',  # 12.5秒, 30秒
            r'(\d+\.?\d*)\s*s\b',  # 12.5s, 30s (单词边界)
            r'(\d+):(\d{2})',   # 1:23, 5:30 (秒数必须是两位数)
            r'(\d+):(\d{1,2})', # 1:3, 5:30 (允许个位数秒)
            r'(\d+)\s*分\s*(\d+)\s*秒',  # 1分30秒
            r'(\d+)\s*分钟\s*(\d+)\s*秒', # 1分钟30秒
            r'(\d+)\s*分钟?\b',  # 10分钟, 10分
        ]

        # 提取所有时间戳
        all_times = []
        for pattern in time_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:  # 分:秒 或 分秒 格式
                        try:
                            minutes = int(match[0])
                            seconds = int(match[1])
                            
                            # 验证时间合理性
                            if minutes >= 0 and minutes <= 59 and seconds >= 0 and seconds <= 59:
                                total_seconds = minutes * 60 + seconds
                                all_times.append(total_seconds)
                        except ValueError:
                            continue
                    else:  # 只有秒数
                        try:
                            seconds = float(match[0])
                            # 验证秒数合理性（音频通常不会超过几小时）
                            if 0 < seconds <= 7200:  # 2小时以内
                                all_times.append(seconds)
                        except ValueError:
                            continue
                else:  # 单个数字（分钟）
                    try:
                        minutes = int(match)
                        # 验证分钟数合理性
                        if 0 < minutes <= 120:  # 2小时以内
                            seconds = minutes * 60
                            all_times.append(seconds)
                    except ValueError:
                        continue

        if all_times:
            # 过滤异常值：如果最大值超过平均值的3倍，可能是误匹配
            avg_time = sum(all_times) / len(all_times)
            filtered_times = [t for t in all_times if t <= avg_time * 3]
            
            if filtered_times:
                timestamp_info['total_duration'] = max(filtered_times)
                print(f"[INFO] 从文本提取到音频总时长: {timestamp_info['total_duration']:.1f}秒 ({timestamp_info['total_duration']/60:.1f}分钟)")
                
                # 验证总时长的合理性
                if timestamp_info['total_duration'] > 7200:  # 超过2小时
                    print(f"[WARNING] 检测到的时长过长({timestamp_info['total_duration']/60:.1f}分钟)，可能不准确")
                    # 尝试使用更保守的估算
                    reasonable_times = [t for t in filtered_times if t <= 3600]  # 1小时以内
                    if reasonable_times:
                        timestamp_info['total_duration'] = max(reasonable_times)
                        print(f"[INFO] 使用保守估算: {timestamp_info['total_duration']:.1f}秒 ({timestamp_info['total_duration']/60:.1f}分钟)")
            else:
                print(f"[WARNING] 所有检测到的时间戳都被过滤，可能包含误匹配")
        else:
            print(f"[INFO] 未检测到有效的时间戳信息")

    except Exception as e:
        print(f"[WARNING] 时间戳解析失败: {str(e)}")

    return timestamp_info

def _parse_time_string(time_str: str) -> float:
    """
    解析时间字符串，支持以下格式：
    - "X.Y秒" -> X.Y秒
    - "X分Y秒" -> (X*60 + Y)秒
    - "X分" -> X*60秒
    
    Args:
        time_str: 时间字符串
        
    Returns:
        时间（秒），解析失败返回-1
    """
    try:
        time_str = time_str.strip()
        
        # 匹配 "X.Y秒" 格式
        if '秒' in time_str and '分' not in time_str:
            seconds = float(time_str.replace('秒', ''))
            return seconds
        
        # 匹配 "X分Y秒" 格式
        if '分' in time_str and '秒' in time_str:
            parts = time_str.split('分')
            minutes = int(parts[0])
            seconds = int(parts[1].replace('秒', ''))
            return minutes * 60 + seconds
        
        # 匹配 "X分" 格式
        if '分' in time_str and '秒' not in time_str:
            minutes = int(time_str.replace('分', ''))
            return minutes * 60
        
        # 尝试直接解析数字
        return float(time_str)
        
    except (ValueError, TypeError):
        return -1

def _add_timestamp_to_chunk(chunk: str, timestamp_info: Dict, chunk_index: int, total_chunks: int) -> str:
    """
    为文本分块添加时间戳信息
    如果文本已经包含时间戳格式 [时间范围：开始时间-结束时间]，则不再添加

    Args:
        chunk: 文本分块
        timestamp_info: 时间戳信息
        chunk_index: 分块索引
        total_chunks: 总分块数

    Returns:
        添加了时间戳信息的文本分块
    """
    # 检查文本是否已经包含时间戳格式
    import re
    if re.search(r'\[时间范围：[^\]]+\]', chunk):
        print(f"[INFO] 文本分块 {chunk_index + 1} 已包含时间戳，跳过添加")
        return chunk
    
    if not timestamp_info or timestamp_info['total_duration'] <= 0:
        return chunk

    # 如果有真实的时间段信息，优先使用
    if timestamp_info.get('segments'):
        # 根据文本内容匹配时间段
        chunk_timestamps = _find_chunk_timestamps(chunk, timestamp_info['segments'])
        if chunk_timestamps:
            start_time = chunk_timestamps['start']
            end_time = chunk_timestamps['end']
            
            # 格式化时间戳
            start_timestamp = _format_timestamp(start_time)
            end_timestamp = _format_timestamp(end_time)
            
            # 在分块开头添加时间戳信息
            timestamp_header = f"**时间范围：{start_timestamp} - {end_timestamp}**\n\n"
            return timestamp_header + chunk

    # 备用方案：按比例估算时间范围
    total_duration = timestamp_info['total_duration']

    # 计算当前分块的时间范围
    if total_chunks == 1:
        start_time = 0
        end_time = total_duration
    else:
        # 根据分块位置估算时间范围
        chunk_ratio = chunk_index / total_chunks
        next_chunk_ratio = (chunk_index + 1) / total_chunks

        start_time = chunk_ratio * total_duration
        end_time = next_chunk_ratio * total_duration

    # 格式化时间戳
    start_timestamp = _format_timestamp(start_time)
    end_timestamp = _format_timestamp(end_time)

    # 在分块开头添加时间戳信息
    timestamp_header = f"**时间范围：{start_timestamp} - {end_timestamp}**\n\n"

    return timestamp_header + chunk

def _find_chunk_timestamps(chunk: str, segments: list) -> Dict:
    """
    根据文本分块内容匹配对应的时间段
    
    Args:
        chunk: 文本分块
        segments: 时间段列表，每个元素包含start, end, text
        
    Returns:
        匹配的时间段信息，如果没有匹配则返回None
    """
    if not segments:
        return None
    
    # 计算分块中每个字符的匹配度
    best_match = None
    best_score = 0
    
    for segment in segments:
        segment_text = segment.get('text', '').strip()
        if not segment_text:
            continue
            
        # 计算文本相似度（简单的字符匹配）
        chunk_words = set(chunk.lower().split())
        segment_words = set(segment_text.lower().split())
        
        if chunk_words and segment_words:
            # 计算Jaccard相似度
            intersection = len(chunk_words.intersection(segment_words))
            union = len(chunk_words.union(segment_words))
            similarity = intersection / union if union > 0 else 0
            
            if similarity > best_score:
                best_score = similarity
                best_match = segment
    
    # 如果相似度太低，返回None
    if best_score < 0.1:  # 10%的相似度阈值
        return None
        
    return best_match

def _format_timestamp(seconds: float) -> str:
    """
    格式化时间戳为易读格式

    Args:
        seconds: 秒数

    Returns:
        格式化的时间字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    else:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if secs == 0:
            return f"{minutes}分"
        else:
            return f"{minutes}分{secs}秒"

def _generate_fallback_summary(chunk_with_timestamp: str, chunk_index: int) -> str:
    """
    生成备用摘要，当API调用失败时使用

    Args:
        chunk_with_timestamp: 带时间戳的文本分块
        chunk_index: 分块索引

    Returns:
        备用摘要内容
    """
    # 提取时间戳信息
    import re
    timestamp_match = re.search(r'\*\*时间范围：(.+?)\*\*', chunk_with_timestamp)
    timestamp_info = timestamp_match.group(1) if timestamp_match else "时间未知"

    # 简单的文本处理：提取关键信息
    text_content = chunk_with_timestamp.replace(timestamp_match.group(0) if timestamp_match else "", "").strip()

    # 生成基本的备用摘要
    fallback_summary = f"""### 音频分块 {chunk_index} 摘要 {timestamp_info}

**注意：由于API调用超时，以下是基于文本内容的简化摘要**

#### 主要内容
{text_content[:200]}{'...' if len(text_content) > 200 else ''}

#### 关键信息
- 文本长度：{len(text_content)} 字符
- 时间范围：{timestamp_info}
- 处理状态：API超时，使用备用摘要

---
"""
    return fallback_summary 

def _add_paragraph_ids(text: str) -> str:
    """
    为文本的每一行添加ID标识
    
    Args:
        text: 原始文本
        
    Returns:
        添加了行ID的文本
    """
    # 按行分割文本
    lines = text.strip().split('\n')
    
    # 为每一行添加ID
    text_with_ids = ""
    for i, line in enumerate(lines):
        if line.strip():  # 跳过空行
            # 生成行ID，格式：P001, P002, P003...
            line_id = f"P{(i+1):03d}"
            
            # 在行开头添加ID标识
            text_with_ids += f"[{line_id}] {line}\n"
        else:
            # 保留空行，不添加ID
            text_with_ids += '\n'
    
    print(f"[INFO] 为 {len([l for l in lines if l.strip()])} 行内容添加了ID标识")
    return text_with_ids 