import json
import os
import time
from typing import List, Dict
import logging
from datetime import datetime
from openai import OpenAI
from util._save_raw_text import image_to_base64

logger = logging.getLogger(__name__)

class VideoSummaryGenerator:
    """视频摘要生成器"""
    
    def __init__(self, llm_api=None):
        """
        初始化摘要生成器
        
        Args:
            llm_api: 大语言模型API接口（可选，默认使用豆包大模型）
        """
        if llm_api is None:
            # 使用豆包大模型作为默认配置
            self.llm_api = DoubaoLLMAPI()
        else:
            self.llm_api = llm_api
    
    def generate_comprehensive_summary(self, aligned_content: List[Dict], ppt_frames_dir: str = None) -> Dict:
        """
        生成综合摘要（支持图文结合）
        
        Args:
            aligned_content: 同步后的内容列表
            ppt_frames_dir: PPT页面图片目录路径
            
        Returns:
            综合摘要字典
        """
        print("正在生成综合摘要...")
        logger.info("开始生成综合摘要...")
        
        # 1. 生成概览（支持图文结合）
        overview = self._generate_overview(aligned_content, ppt_frames_dir)
        
        # 2. 提取关键要点
        key_points = self._extract_key_points(aligned_content)
        
        # 3. 生成时间线
        timeline = self._generate_timeline(aligned_content)
        
        # 4. 生成详细内容
        detailed_content = self._generate_detailed_content(aligned_content)
        
        # 5. 生成学习建议
        learning_suggestions = self._generate_learning_suggestions(aligned_content)
        
        summary = {
            'overview': overview,
            'key_points': key_points,
            'timeline': timeline,
            'detailed_content': detailed_content,
            'learning_suggestions': learning_suggestions,
            'statistics': self._generate_statistics(aligned_content),
            'generated_at': datetime.now().isoformat()
        }
        
        print("综合摘要生成完成！")
        logger.info("综合摘要生成完成")
        return summary
    
    def _generate_overview(self, aligned_content: List[Dict], ppt_frames_dir: str = None) -> str:
        """生成内容概览（支持图文结合）"""
        if not aligned_content:
            return "无内容可生成概览"
        
        # 收集所有文本内容
        all_texts = []
        for content in aligned_content:
            # PPT内容
            if content.get('slide_content'):
                all_texts.append(f"PPT内容: {content['slide_content']}")
            
            # 音频内容
            if content.get('audio_content') and content['audio_content'].get('text'):
                all_texts.append(f"音频讲解: {content['audio_content']['text']}")
        
        combined_text = "\n".join(all_texts)
        
        # 收集PPT页面图片
        image_paths = []
        if ppt_frames_dir and os.path.exists(ppt_frames_dir):
            try:
                # 获取所有PPT页面图片
                for file in os.listdir(ppt_frames_dir):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        image_paths.append(os.path.join(ppt_frames_dir, file))
                # 按文件名排序
                image_paths.sort()
                logger.info(f"找到 {len(image_paths)} 个PPT页面图片")
            except Exception as e:
                logger.error(f"读取PPT页面图片失败: {e}")
        
        # 使用多模态大模型生成概览
        if image_paths and self.llm_api:
            return self._generate_multimodal_overview(combined_text, ppt_frames_dir, aligned_content)
        else:
            # 如果没有图片，使用纯文本模式
            return self._generate_text_overview(combined_text)
    
    def _generate_multimodal_overview(self, transcript: str, ppt_frames_dir: str = None, aligned_content: List[Dict] = None) -> str:
        """生成多模态概述（文本+图片）- 支持分批处理"""
        try:
            if not ppt_frames_dir or not os.path.exists(ppt_frames_dir):
                logger.warning("PPT图片目录不存在，使用文本模式")
                return self._generate_text_overview(transcript)
            
            # 获取PPT图片
            ppt_images = []
            for file in os.listdir(ppt_frames_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    ppt_images.append(os.path.join(ppt_frames_dir, file))
            
            if not ppt_images:
                logger.warning("未找到PPT图片，使用文本模式")
                return self._generate_text_overview(transcript)
            
            # 按文件名排序（确保时间顺序）
            ppt_images.sort()
            logger.info(f"找到 {len(ppt_images)} 个PPT页面图片")
            
            # 判断是否需要分批处理
            max_images_per_batch = 50
            if len(ppt_images) > max_images_per_batch:
                logger.info(f"图片数量过多({len(ppt_images)})，启用分批处理模式")
                return self._generate_batched_multimodal_overview(transcript, ppt_images, aligned_content, max_images_per_batch)
            else:
                logger.info(f"图片数量适中({len(ppt_images)})，使用单次处理模式")
                return self._generate_single_multimodal_overview(transcript, ppt_images)
            
        except Exception as e:
            logger.error(f"多模态概述生成失败: {e}")
            return self._generate_text_overview(transcript)
    
    def _generate_single_multimodal_overview(self, transcript: str, ppt_images: List[str]) -> str:
        """单次处理多模态概述（适用于图片数量较少的情况）"""
        try:
            # 转换图片为base64
            base64_images = []
            for img_path in ppt_images:
                try:
                    base64_img = image_to_base64(img_path)
                    if base64_img is not None:
                        base64_images.append(base64_img)
                    else:
                        logger.warning(f"图片转换返回None: {img_path}")
                except Exception as e:
                    logger.warning(f"转换图片失败 {img_path}: {e}")
                    continue
            
            if not base64_images:
                logger.warning("图片转换失败，使用文本模式")
                return self._generate_text_overview(transcript)
            
            # 构造多模态提示词
            prompt = f"""请分析这个教学视频的完整内容，包括：

1. **音频转录文本**：{transcript[:2000]}{'...' if len(transcript) > 2000 else ''}

2. **PPT图片内容**：请仔细分析提供的{len(base64_images)}张PPT图片，提取每张图片中的：
   - 标题和副标题
   - 正文内容（包括所有文字、数字、公式等）
   - 图表、图片、流程图等视觉元素
   - 要点和列表项
   - 任何其他重要信息

**重要提示**：
- 由于PPT页面检测算法可能存在重复检测的情况，部分图片内容可能相似或重复
- 请识别重复或相似的图片内容，避免在摘要中重复描述相同的信息
- 重点关注内容的变化和新出现的知识点
- 如果发现重复内容，请简要提及即可，重点突出新增或变化的部分

**时间戳要求**：
- 每个知识点和概念的开头必须标注对应的时间范围（格式：**时间戳：XX分XX秒-XX分XX秒**）
- 时间戳信息应该基于PPT图片的文件名中的时间信息或音频转录的时间信息
- 如果无法确定具体时间，请标注"时间戳：未知"或估算时间范围

请生成一个全面的教学视频摘要，包括：
- 视频主题和教学目标
- 主要知识点和概念（每个知识点开头标注时间戳：XX分XX秒-XX分XX秒）
- 重要公式、数据或结论（标注时间戳）
- 教学逻辑和结构
- 关键要点总结（标注时间戳）

请确保从PPT图片中提取所有可见的文本内容和视觉信息，结合音频转录内容，生成完整、准确且无重复的教学视频摘要。"""

            # 调用多模态API
            logger.info(f"开始调用豆包多模态API，图片数量: {len(base64_images)}")
            result = self.llm_api.generate_multimodal(prompt, base64_images)
            
            if result is None:
                logger.warning("多模态API返回空结果，使用文本模式")
                return self._generate_text_overview(transcript)
            
            return result
            
        except Exception as e:
            logger.error(f"单次多模态概述生成失败: {e}")
            return self._generate_text_overview(transcript)
    
    def _generate_batched_multimodal_overview(self, transcript: str, ppt_images: List[str], 
                                            aligned_content: List[Dict], max_images_per_batch: int = 50) -> str:
        """分批处理多模态概述（适用于图片数量较多的情况）"""
        try:
            logger.info(f"开始分批处理，每批最多 {max_images_per_batch} 张图片")
            
            # 创建图片到内容的映射
            image_content_map = self._create_image_content_mapping(ppt_images, aligned_content)
            
            # 分批处理
            batch_summaries = []
            total_batches = (len(ppt_images) + max_images_per_batch - 1) // max_images_per_batch
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * max_images_per_batch
                end_idx = min(start_idx + max_images_per_batch, len(ppt_images))
                batch_images = ppt_images[start_idx:end_idx]
                
                logger.info(f"处理批次 {batch_idx + 1}/{total_batches}: 图片 {start_idx + 1}-{end_idx}")
                
                # 获取对应批次的文本内容
                batch_text_content = self._get_batch_text_content(batch_images, image_content_map)
                
                # 转换图片为base64
                base64_images = []
                for img_path in batch_images:
                    try:
                        base64_img = image_to_base64(img_path)
                        if base64_img is not None:
                            base64_images.append(base64_img)
                    except Exception as e:
                        logger.warning(f"转换图片失败 {img_path}: {e}")
                        continue
                
                if not base64_images:
                    logger.warning(f"批次 {batch_idx + 1} 图片转换失败，跳过")
                    continue
                
                # 构造批次提示词
                batch_prompt = f"""请分析这个教学视频片段的内容（第 {batch_idx + 1} 批，共 {total_batches} 批），包括：

1. **音频转录文本**：{batch_text_content[:1500]}{'...' if len(batch_text_content) > 1500 else ''}

2. **PPT图片内容**：请仔细分析提供的{len(base64_images)}张PPT图片，提取每张图片中的：
   - 标题和副标题
   - 正文内容（包括所有文字、数字、公式等）
   - 图表、图片、流程图等视觉元素
   - 要点和列表项
   - 任何其他重要信息

**重要提示**：
- 由于PPT页面检测算法可能存在重复检测的情况，部分图片内容可能相似或重复
- 请识别重复或相似的图片内容，避免在分析中重复描述相同的信息
- 重点关注内容的变化和新出现的知识点
- 如果发现重复内容，请简要提及即可，重点突出新增或变化的部分

**时间戳要求**：
- 每个知识点和概念的开头必须标注对应的时间范围（格式：**时间戳：XX分XX秒-XX分XX秒**）
- 时间戳信息应该基于PPT图片的文件名中的时间信息或音频转录的时间信息
- 如果无法确定具体时间，请标注"时间戳：未知"或估算时间范围

请生成这个片段的详细分析，包括：
- 主要知识点和概念（每个知识点开头标注时间戳：XX分XX秒-XX分XX秒）
- 重要公式、数据或结论（标注时间戳）
- 教学逻辑和结构
- 关键要点总结（标注时间戳）

请确保从PPT图片中提取所有可见的文本内容和视觉信息，结合音频转录内容，生成准确且无重复的分析。"""

                # 调用多模态API
                logger.info(f"调用豆包多模态API处理批次 {batch_idx + 1}，图片数量: {len(base64_images)}")
                batch_result = self.llm_api.generate_multimodal(batch_prompt, base64_images)
                
                if batch_result:
                    batch_summaries.append({
                        'batch_index': batch_idx + 1,
                        'total_batches': total_batches,
                        'content': batch_result
                    })
                    logger.info(f"批次 {batch_idx + 1} 处理完成")
                else:
                    logger.warning(f"批次 {batch_idx + 1} API返回空结果")
            
            # 整合所有批次的摘要
            if not batch_summaries:
                logger.warning("所有批次处理失败，使用文本模式")
                return self._generate_text_overview(transcript)
            
            return self._combine_batch_summaries(batch_summaries, transcript)
            
        except Exception as e:
            logger.error(f"分批多模态概述生成失败: {e}")
            return self._generate_text_overview(transcript)
    
    def _create_image_content_mapping(self, ppt_images: List[str], aligned_content: List[Dict]) -> Dict:
        """创建图片到内容的映射关系"""
        image_content_map = {}
        
        if not aligned_content:
            return image_content_map
        
        for content in aligned_content:
            slide_index = content.get('slide_index', 0)
            slide_content = content.get('slide_content', '')
            audio_content = content.get('audio_content', {}).get('text', '')
            
            # 查找对应的图片文件
            for img_path in ppt_images:
                img_name = os.path.basename(img_path)
                # 从文件名中提取slide_index（格式：slide_001_12.5s_stable.jpg）
                if f"slide_{slide_index:03d}" in img_name:
                    image_content_map[img_path] = {
                        'slide_content': slide_content,
                        'audio_content': audio_content,
                        'slide_index': slide_index
                    }
                    break
        
        logger.info(f"创建了 {len(image_content_map)} 个图片内容映射")
        return image_content_map
    
    def _get_batch_text_content(self, batch_images: List[str], image_content_map: Dict) -> str:
        """获取批次对应的文本内容"""
        batch_texts = []
        
        for img_path in batch_images:
            if img_path in image_content_map:
                content_info = image_content_map[img_path]
                slide_content = content_info['slide_content']
                audio_content = content_info['audio_content']
                slide_index = content_info['slide_index']
                
                # 从文件名中提取时间戳信息
                img_name = os.path.basename(img_path)
                timestamp_info = self._extract_timestamp_from_filename(img_name)
                
                if slide_content:
                    batch_texts.append(f"PPT页面 {slide_index} {timestamp_info}: {slide_content}")
                if audio_content:
                    batch_texts.append(f"音频讲解 {timestamp_info}: {audio_content}")
        
        return "\n".join(batch_texts)
    
    def _extract_timestamp_from_filename(self, filename: str) -> str:
        """从文件名中提取时间戳信息"""
        try:
            # 文件名格式：slide_001_12.5s_stable.jpg
            if '_' in filename and 's' in filename:
                parts = filename.split('_')
                for part in parts:
                    if part.endswith('s') and part[:-1].replace('.', '').isdigit():
                        seconds = float(part[:-1])
                        minutes = int(seconds // 60)
                        secs = int(seconds % 60)
                        return f"({minutes:02d}分{secs:02d}秒)"
            return "(时间未知)"
        except:
            return "(时间未知)"
    
    def _combine_batch_summaries(self, batch_summaries: List[Dict], original_transcript: str) -> str:
        """整合所有批次的摘要"""
        try:
            logger.info("开始整合批次摘要...")
            
            # 按批次顺序排序
            batch_summaries.sort(key=lambda x: x['batch_index'])
            
            # 准备整合内容
            combined_content = f"""# 教学视频内容分析（分批处理结果）

## 处理信息
- 总批次数: {batch_summaries[0]['total_batches']}
- 处理方式: 分批多模态分析
- 原始音频长度: {len(original_transcript)} 字符

## 各批次分析结果

"""
            
            for batch in batch_summaries:
                combined_content += f"""### 第 {batch['batch_index']} 批分析结果

{batch['content']}

---
"""
            
                        # 生成最终整合摘要
            combined_content += f"""

## 整体摘要

请基于以上各批次的分析结果，生成一个完整的教学视频摘要，包括：
- 视频主题和教学目标
- 主要知识点和概念（每个知识点开头标注时间戳：XX分XX秒-XX分XX秒）
- 重要公式、数据或结论（标注时间戳）
- 教学逻辑和结构
- 关键要点总结（标注时间戳）

**重要提示**：
- 由于各批次可能存在重复或相似的内容，请识别并合并重复信息
- 避免在最终摘要中重复描述相同的内容
- 重点关注内容的递进和变化
- 生成连贯、完整且无重复的教学视频摘要

**时间戳要求**：
- 每个知识点和概念的开头必须标注对应的时间范围（格式：**时间戳：XX分XX秒-XX分XX秒**）
- 时间戳信息应该基于各批次分析中的时间信息
- 如果无法确定具体时间，请标注"时间戳：未知"或估算时间范围

请确保整合所有批次的重要信息，生成连贯、完整且无重复的教学视频摘要。"""
            
            # 使用文本API生成最终整合摘要
            if self.llm_api:
                final_summary = self.llm_api.generate_text(combined_content)
                if final_summary:
                    return final_summary
            
            # 如果API调用失败，返回原始整合内容
            return combined_content
            
        except Exception as e:
            logger.error(f"整合批次摘要失败: {e}")
            # 返回简单的批次摘要组合
            return "\n\n".join([batch['content'] for batch in batch_summaries])
    
    def _generate_text_overview(self, text_content: str) -> str:
        """生成纯文本概览"""
        try:
            prompt = f"""
            你是一个专业的教学视频内容分析专家。请根据以下教学视频的PPT内容和音频讲解，生成一份结构化的内容概览。

            【视频内容】
            {text_content[:3000]}  # 限制长度避免API限制

            【分析要求】
            1. 识别视频的主要教学主题
            2. 提取核心知识点和重要概念
            3. 总结关键学习要点
            4. 分析PPT内容与音频讲解的关联性

            【输出格式】
            请使用Markdown格式输出，包含以下部分：

            ## 教学主题
            [简要描述视频的主要教学主题]

            ## 核心知识点
            - [知识点1]
            - [知识点2]
            - [知识点3]
            ...

            ## 关键学习要点
            - [要点1]
            - [要点2]
            - [要点3]
            ...

            ## 内容特点
            [分析PPT内容与音频讲解的特点和关联性]
            """
            
            if self.llm_api:
                overview = self.llm_api.generate_text(prompt)
                return overview.strip() if overview else "文本概览生成失败"
            else:
                return self._generate_simple_overview_from_text(text_content)
                
        except Exception as e:
            logger.error(f"文本概览生成失败: {e}")
            return self._generate_simple_overview_from_text(text_content)
    
    def _generate_simple_overview_from_text(self, text_content: str) -> str:
        """从文本生成简单概览"""
        lines = text_content.split('\n')
        content_lines = [line.strip() for line in lines if len(line.strip()) > 10]
        
        if not content_lines:
            return "无内容可生成概览"
        
        # 提取前几行作为概览
        summary_lines = content_lines[:5]
        summary = "\n\n".join(summary_lines)
        
        if len(summary) > 1000:
            summary = summary[:1000] + "..."
        
        return f"""
## 内容概览

{summary}

*注：这是基于文本内容的简单概览，如需更详细的图文分析，请确保PPT页面图片可用。*
        """.strip()
    
    def _generate_simple_overview(self, aligned_content: List[Dict]) -> str:
        """生成简单概览"""
        if not aligned_content:
            return "无内容"
        
        # 统计信息
        total_slides = len(aligned_content)
        total_duration = sum([
            content.get('audio_content', {}).get('duration', 0) 
            for content in aligned_content
        ])
        
        # 提取主要主题词
        all_words = []
        for content in aligned_content:
            if content.get('slide_content'):
                all_words.extend(content['slide_content'].split())
        
        # 简单的词频统计
        from collections import Counter
        word_counts = Counter(all_words)
        top_words = [word for word, count in word_counts.most_common(5) if len(word) > 1]
        
        overview = f"""
## 内容概览
- 总PPT页面数: {total_slides}
- 总讲解时长: {total_duration:.1f}秒
- 主要关键词: {', '.join(top_words[:3])}

## 内容结构
本视频包含{total_slides}个PPT页面，涵盖了{', '.join(top_words[:3])}等相关内容。
        """
        
        return overview.strip()
    
    def _extract_key_points(self, aligned_content: List[Dict]) -> List[str]:
        """提取关键要点"""
        key_points = []
        
        for i, content in enumerate(aligned_content):
            slide_text = content.get('slide_content', '')
            audio_text = content.get('audio_content', {}).get('text', '')
            
            # 从PPT内容提取要点
            if slide_text:
                words = slide_text.split()
                if len(words) >= 3:
                    key_points.append(f"第{i+1}页: {words[0]} {words[1]} {words[2]}")
            
            # 从音频内容提取要点
            if audio_text:
                words = audio_text.split()
                if len(words) >= 5:
                    key_points.append(f"讲解要点: {words[0]} {words[1]} {words[2]}")
        
        # 去重并限制数量
        unique_points = list(set(key_points))
        return unique_points[:10]  # 最多10个要点
    
    def _generate_timeline(self, aligned_content: List[Dict]) -> List[Dict]:
        """生成时间线"""
        timeline = []
        
        for i, content in enumerate(aligned_content):
            timestamp = content.get('timestamp', 0)
            duration = content.get('audio_content', {}).get('duration', 0)
            slide_text = content.get('slide_content', '')
            audio_text = content.get('audio_content', {}).get('text', '')
            
            timeline_item = {
                'index': i + 1,
                'timestamp': timestamp,
                'formatted_time': self._format_timestamp(timestamp),
                'duration': duration,
                'slide_summary': slide_text[:50] + "..." if len(slide_text) > 50 else slide_text,
                'audio_summary': audio_text[:100] + "..." if len(audio_text) > 100 else audio_text,
                'key_points': self._extract_segment_key_points(content)
            }
            
            timeline.append(timeline_item)
        
        return timeline
    
    def _extract_segment_key_points(self, content: Dict) -> List[str]:
        """提取单个片段的关键要点"""
        points = []
        
        slide_text = content.get('slide_content', '')
        if slide_text:
            words = slide_text.split()
            if len(words) >= 2:
                points.append(f"PPT: {' '.join(words[:2])}")
        
        audio_text = content.get('audio_content', {}).get('text', '')
        if audio_text:
            words = audio_text.split()
            if len(words) >= 3:
                points.append(f"讲解: {' '.join(words[:3])}")
        
        return points
    
    def _generate_detailed_content(self, aligned_content: List[Dict]) -> List[Dict]:
        """生成详细内容"""
        detailed_content = []
        
        for i, content in enumerate(aligned_content):
            detailed_item = {
                'index': i + 1,
                'timestamp': content.get('timestamp', 0),
                'formatted_time': self._format_timestamp(content.get('timestamp', 0)),
                'slide_content': content.get('slide_content', ''),
                'audio_content': content.get('audio_content', {}).get('text', ''),
                'duration': content.get('audio_content', {}).get('duration', 0),
                'confidence': content.get('audio_content', {}).get('confidence', 0),
                'change_ratio': content.get('change_ratio', 0)
            }
            
            detailed_content.append(detailed_item)
        
        return detailed_content
    
    def _generate_learning_suggestions(self, aligned_content: List[Dict]) -> List[str]:
        """生成学习建议"""
        suggestions = []
        
        # 基于内容长度生成建议
        total_duration = sum([
            content.get('audio_content', {}).get('duration', 0) 
            for content in aligned_content
        ])
        
        if total_duration > 1800:  # 30分钟以上
            suggestions.append("建议分段学习，每次学习15-20分钟")
        elif total_duration > 600:  # 10分钟以上
            suggestions.append("建议一次性完整学习")
        else:
            suggestions.append("内容较短，可以快速浏览")
        
        # 基于PPT页面数量生成建议
        slide_count = len(aligned_content)
        if slide_count > 20:
            suggestions.append("PPT页面较多，建议重点关注核心页面")
        elif slide_count > 10:
            suggestions.append("内容适中，建议按顺序学习")
        else:
            suggestions.append("内容精炼，建议仔细学习每个要点")
        
        # 基于内容类型生成建议
        text_content_count = sum([
            1 for content in aligned_content 
            if content.get('slide_content')
        ])
        
        if text_content_count > slide_count * 0.8:
            suggestions.append("文字内容丰富，建议做好笔记")
        else:
            suggestions.append("图表较多，建议结合讲解理解")
        
        return suggestions
    
    def _generate_statistics(self, aligned_content: List[Dict]) -> Dict:
        """生成统计信息"""
        if not aligned_content:
            return {}
        
        total_slides = len(aligned_content)
        total_duration = sum([
            content.get('audio_content', {}).get('duration', 0) 
            for content in aligned_content
        ])
        
        # 计算平均置信度
        confidences = [
            content.get('audio_content', {}).get('confidence', 0) 
            for content in aligned_content 
            if content.get('audio_content')
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # 计算平均变化率
        change_ratios = [
            content.get('change_ratio', 0) 
            for content in aligned_content
        ]
        avg_change_ratio = sum(change_ratios) / len(change_ratios) if change_ratios else 0
        
        # 统计有文字内容的页面
        text_content_count = sum([
            1 for content in aligned_content 
            if content.get('slide_content')
        ])
        
        return {
            'total_slides': total_slides,
            'total_duration': total_duration,
            'avg_confidence': avg_confidence,
            'avg_change_ratio': avg_change_ratio,
            'text_content_count': text_content_count,
            'text_content_ratio': text_content_count / total_slides if total_slides > 0 else 0
        }
    
    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def save_summary(self, summary: Dict, output_path: str):
        """
        保存摘要到文件
        
        Args:
            summary: 摘要字典
            output_path: 输出文件路径
        """
        # 检查summary是否为None
        if summary is None:
            logger.error("无法保存摘要：summary为None")
            return
            
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存为JSON格式
        json_path = output_path.replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 保存为Markdown格式
        markdown_content = self._generate_markdown_summary(summary)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"摘要已保存到: {output_path}")
        logger.info(f"JSON格式已保存到: {json_path}")
    
    def _generate_markdown_summary(self, summary: Dict) -> str:
        """生成Markdown格式的摘要"""
        markdown = f"""# 教学视频内容摘要

生成时间: {summary.get('generated_at', '未知')}

## 统计信息
- 总PPT页面数: {summary.get('statistics', {}).get('total_slides', 0)}
- 总讲解时长: {summary.get('statistics', {}).get('total_duration', 0):.1f}秒
- 平均置信度: {summary.get('statistics', {}).get('avg_confidence', 0):.2f}
- 文字内容页面: {summary.get('statistics', {}).get('text_content_count', 0)}

## 内容概览
{summary.get('overview', '无概览')}

## 关键要点
"""
        
        for i, point in enumerate(summary.get('key_points', []), 1):
            markdown += f"{i}. {point}\n"
        
        markdown += "\n## 时间线\n"
        for item in summary.get('timeline', []):
            markdown += f"""
### {item['index']}. {item['formatted_time']} ({item['duration']:.1f}秒)
**PPT内容:** {item['slide_summary']}
**讲解内容:** {item['audio_summary']}
"""
        
        markdown += "\n## 详细内容\n"
        for item in summary.get('detailed_content', []):
            markdown += f"""
### {item['index']}. {item['formatted_time']}
**PPT内容:**
{item['slide_content']}

**讲解内容:**
{item['audio_content']}

---
"""
        
        markdown += "\n## 学习建议\n"
        for suggestion in summary.get('learning_suggestions', []):
            markdown += f"- {suggestion}\n"
        
        return markdown 

class DoubaoLLMAPI:
    """豆包大模型API封装"""
    
    def __init__(self):
        """初始化豆包API配置"""
        # 从配置文件获取豆包API配置
        from util.config_manager import get_doubao_config
        doubao_config = get_doubao_config()
        self.api_key = doubao_config.get('api_key')
        self.base_url = doubao_config.get('base_url')
        self.model = doubao_config.get('model')
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
    
    def generate_text(self, prompt: str) -> str:
        """
        使用豆包大模型生成文本
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的文本内容
        """
        # 导入用量统计器
        try:
            from util.llm_usage_tracker import record_doubao_usage
            use_tracking = True
        except ImportError:
            use_tracking = False
        
        start_time = time.time()
        success = False
        error_message = ""
        
        try:
            # 估算输入token数
            input_tokens = len(prompt) * 1.5  # 简单估算
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的教学视频内容分析专家。请生成结构化、简洁、包含要点的Markdown格式摘要。保留关键数据和专业术语。使用中文输出结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=20000,
                timeout=60
            )
            content = response.choices[0].message.content
            success = True
            
            # 获取真实的token数（如果API返回）
            input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else int(input_tokens)
            output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else int(len(content) * 1.5)
            total_tokens = response.usage.total_tokens if hasattr(response, 'usage') and response.usage else int(input_tokens + output_tokens)
            
            # 记录用量统计
            if use_tracking:
                api_duration = time.time() - start_time
                record_doubao_usage(
                    input_tokens=int(input_tokens),
                    output_tokens=int(output_tokens),
                    duration=api_duration,
                    success=True,
                    metadata={
                        'model_type': 'text_only',
                        'prompt_length': len(prompt),
                        'token_source': 'api_response' if hasattr(response, 'usage') and response.usage else 'estimated'
                    }
                )
            
            return content.strip() if content else ""
        except Exception as e:
            error_message = f"豆包API调用失败: {e}"
            logger.error(error_message)
            
            # 记录失败统计
            if use_tracking:
                api_duration = time.time() - start_time
                record_doubao_usage(
                    input_tokens=int(input_tokens) if 'input_tokens' in locals() else 0,
                    output_tokens=0,
                    duration=api_duration,
                    success=False,
                    error_message=error_message
                )
            
            return f"摘要生成失败: {str(e)}"
    
    def generate_multimodal(self, prompt: str, image_data: List[str]) -> str:
        """
        使用豆包多模态大模型生成图文结合内容
        
        Args:
            prompt: 提示词
            image_data: Base64编码的图片数据列表
            
        Returns:
            str: 生成的文本内容
        """
        try:
            # 估算输入token数（文本 + 图片）
            text_content = prompt
            image_count = len(image_data)
            
            # 估算token数：文本 + 图片（每张图片约1000 tokens）
            estimated_input_tokens = len(text_content) // 4 + image_count * 1000
            
            start_time = time.time()
            
            # 构造多模态消息
            content = []
            content.append({"type": "text", "text": prompt})
            
            # 添加图片
            for i, base64_img in enumerate(image_data):
                if base64_img is None:
                    logger.warning(f"跳过第{i+1}张图片：base64数据为空")
                    continue
                logger.debug(f"添加第{i+1}张图片，base64长度: {len(base64_img)}")
                content.append({
                    "type": "image_url", 
                    "image_url": {"url": base64_img}
                })
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                temperature=0.3,
                max_tokens=20000,
                timeout=120
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if response and response.choices:
                result = response.choices[0].message.content
                
                # 记录使用情况
                actual_output_tokens = response.usage.completion_tokens if response.usage else 0
                actual_input_tokens = response.usage.prompt_tokens if response.usage else estimated_input_tokens
                
                # 记录到使用统计
                from .llm_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                if tracker:
                    tracker.record_doubao_multimodal_usage(
                        input_tokens=actual_input_tokens,
                        output_tokens=actual_output_tokens,
                        duration=duration,
                        success=True
                    )
                
                logger.info(f"豆包多模态API调用成功，输入tokens: {actual_input_tokens}, 输出tokens: {actual_output_tokens}, 耗时: {duration:.2f}秒")
                return result
            else:
                logger.error("豆包多模态API返回空结果")
                return None
                
        except Exception as e:
            logger.error(f"豆包多模态API调用失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"API响应状态码: {e.response.status_code}")
                logger.error(f"API响应内容: {e.response.text}")
            
            # 记录失败情况
            from .llm_usage_tracker import get_global_tracker
            tracker = get_global_tracker()
            if tracker:
                tracker.record_doubao_multimodal_usage(
                    input_tokens=estimated_input_tokens,
                    output_tokens=0,
                    duration=time.time() - start_time if 'start_time' in locals() else 0,
                    success=False,
                    error_message=str(e)
                )
            
            return None 