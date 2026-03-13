import os
import json
from typing import List, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AudioVideoSynchronizer:
    """音频视频同步器"""
    
    def __init__(self):
        """初始化同步器"""
        pass
    
    def sync_audio_with_video(self, video_path: str, ppt_slides: List[Dict], 
                            audio_transcript: List[Dict]) -> List[Dict]:
        """
        将音频转写与视频内容同步
        
        Args:
            video_path: 视频文件路径
            ppt_slides: PPT页面列表
            audio_transcript: 音频转写结果
            
        Returns:
            同步后的内容列表
        """
        logger.info("开始音频视频同步...")
        
        aligned_content = []
        
        for i, slide in enumerate(ppt_slides):
            slide_time = slide['timestamp']
            
            # 找到对应时间段的音频内容
            corresponding_audio = self._find_audio_segment(
                audio_transcript, slide_time, ppt_slides, i
            )
            
            # 这里使用基本信息作为占位符
            slide_text = f"PPT页面 {slide.get('slide_index', i+1)} (时间戳: {slide_time:.1f}s)"
            
            aligned_content.append({
                'timestamp': slide_time,
                'slide_content': slide_text,
                'audio_content': corresponding_audio,
                'frame': slide['frame'],
                'slide_index': slide.get('slide_index', i+1),
                'change_ratio': slide['change_ratio'],
                'is_stable': slide.get('is_stable', True),
                'stability_method': slide.get('stability_method', 'content_based'),
                'content_completeness': slide.get('content_completeness', 0.0)
            })
        
        logger.info(f"同步完成，共处理 {len(aligned_content)} 个内容片段")
        return aligned_content
    
    def _find_audio_segment(self, audio_transcript: List[Dict], slide_time: float,
                           ppt_slides: List[Dict], slide_index: int) -> Optional[Dict]:
        """
        找到对应时间段的音频内容
        
        Args:
            audio_transcript: 音频转写结果
            slide_time: PPT页面时间戳
            ppt_slides: PPT页面列表
            slide_index: 当前PPT页面索引
            
        Returns:
            对应的音频内容
        """
        # 确定时间窗口
        start_time = slide_time
        
        # 计算结束时间（下一个PPT页面的时间，或者视频结束）
        if slide_index + 1 < len(ppt_slides):
            end_time = ppt_slides[slide_index + 1]['timestamp']
        else:
            # 最后一个PPT页面，使用音频转写的结束时间
            if audio_transcript:
                end_time = audio_transcript[-1].get('end_time', start_time + 60)
            else:
                end_time = start_time + 60
        
        # 查找时间窗口内的音频内容
        audio_segments = []
        for segment in audio_transcript:
            segment_start = segment.get('start_time', 0)
            segment_end = segment.get('end_time', segment_start + 10)
            
            # 检查是否有重叠
            if (segment_start < end_time and segment_end > start_time):
                # 计算重叠部分
                overlap_start = max(segment_start, start_time)
                overlap_end = min(segment_end, end_time)
                
                audio_segments.append({
                    'text': segment.get('text', ''),
                    'start_time': overlap_start,
                    'end_time': overlap_end,
                    'duration': overlap_end - overlap_start,
                    'confidence': segment.get('confidence', 0)
                })
        
        if audio_segments:
            # 合并音频片段
            combined_text = ' '.join([seg['text'] for seg in audio_segments])
            total_duration = sum([seg['duration'] for seg in audio_segments])
            avg_confidence = sum([seg['confidence'] for seg in audio_segments]) / len(audio_segments)
            
            return {
                'text': combined_text,
                'start_time': start_time,
                'end_time': end_time,
                'duration': total_duration,
                'confidence': avg_confidence,
                'segments': audio_segments
            }
        
        return None
    

    
    def generate_timeline(self, aligned_content: List[Dict]) -> List[Dict]:
        """
        生成时间线
        
        Args:
            aligned_content: 同步后的内容
            
        Returns:
            时间线列表
        """
        timeline = []
        
        for i, content in enumerate(aligned_content):
            timeline_item = {
                'index': i + 1,
                'timestamp': content['timestamp'],
                'duration': content['audio_content'].get('duration', 0) if content['audio_content'] else 0,
                'slide_summary': self._generate_slide_summary(content['slide_content']),
                'audio_summary': self._generate_audio_summary(content['audio_content']) if content['audio_content'] else "",
                'key_points': self._extract_key_points(content)
            }
            
            timeline.append(timeline_item)
        
        return timeline
    
    def _generate_slide_summary(self, slide_text: str) -> str:
        """生成PPT页面摘要"""
        if not slide_text:
            return "无文字内容"
        
        # 现在slide_text是占位符，包含页面索引和时间戳信息
        # 直接返回这个信息作为摘要
        return slide_text
    
    def _generate_audio_summary(self, audio_content: Dict) -> str:
        """生成音频内容摘要"""
        if not audio_content or not audio_content.get('text'):
            return "无音频内容"
        
        text = audio_content['text']
        
        # 简单的摘要生成（取前100个字符）
        if len(text) > 100:
            return text[:100] + "..."
        
        return text
    
    def _extract_key_points(self, content: Dict) -> List[str]:
        """提取关键要点"""
        key_points = []
        
        # 从PPT内容中提取要点
        slide_text = content.get('slide_content', '')
        if slide_text:
            # 简单的关键词提取（这里可以后续优化）
            words = slide_text.split()
            if len(words) > 3:
                key_points.append(f"PPT要点: {words[0]} {words[1]} {words[2]}")
        
        # 从音频内容中提取要点
        audio_content = content.get('audio_content')
        if audio_content and audio_content.get('text'):
            audio_text = audio_content['text']
            words = audio_text.split()
            if len(words) > 5:
                key_points.append(f"讲解要点: {words[0]} {words[1]} {words[2]}")
        
        return key_points
    
    def save_sync_results(self, aligned_content: List[Dict], output_path: str):
        """
        保存同步结果
        
        Args:
            aligned_content: 同步后的内容
            output_path: 输出文件路径
        """
        # 准备保存的数据
        save_data = {
            'sync_time': datetime.now().isoformat(),
            'total_segments': len(aligned_content),
            'segments': []
        }
        
        for content in aligned_content:
            segment_data = {
                'timestamp': content['timestamp'],
                'slide_content': content['slide_content'],
                'audio_content': content['audio_content'],
                'change_ratio': content['change_ratio']
            }
            save_data['segments'].append(segment_data)
        
        # 保存为JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"同步结果已保存到: {output_path}")

def load_audio_transcript(transcript_path: str) -> List[Dict]:
    """
    加载音频转写结果
    
    Args:
        transcript_path: 转写文件路径
        
    Returns:
        转写结果列表
    """
    if not os.path.exists(transcript_path):
        logger.warning(f"转写文件不存在: {transcript_path}")
        return []
    
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 根据文件格式解析
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'segments' in data:
            return data['segments']
        else:
            logger.warning(f"未知的转写文件格式: {transcript_path}")
            return []
    
    except Exception as e:
        logger.error(f"加载转写文件失败: {e}")
        return []

def format_timestamp(seconds: float) -> str:
    """
    格式化时间戳
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串 (MM:SS)
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}" 