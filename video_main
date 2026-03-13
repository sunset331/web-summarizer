"""
教学视频内容理解主程序
支持PPT页面检测、音频转写、内容同步和摘要生成
"""

import os
import sys
import logging
from typing import Dict, List
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2
from PIL import Image

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from util.video_utils import VideoProcessor
from util.audio_video_sync import AudioVideoSynchronizer
from util.video_summary import VideoSummaryGenerator
from util.audio_utils import transcribe_audio_from_video

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_processing.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VideoContentAnalyzer:
    """视频内容分析器主类"""
    
    def __init__(self, llm_api=None):
        """
        初始化视频内容分析器
        
        Args:
            llm_api: 大语言模型API接口（可选，默认使用豆包大模型）
        """
        self.video_processor = VideoProcessor()
        self.synchronizer = AudioVideoSynchronizer()
        self.summary_generator = VideoSummaryGenerator(llm_api)
        
        # 初始化LLM用量统计器（输出目录将在process_teaching_video中设置）
        try:
            from util.llm_usage_tracker import get_global_tracker
            self.usage_tracker = get_global_tracker()
        except ImportError:
            self.usage_tracker = None
        
        logger.info("视频内容分析器初始化完成")
        logger.info("音频处理: 讯飞API")
        logger.info("摘要生成: 豆包大模型")
    
    def process_teaching_video(self, video_path: str, output_dir: str = None, 
                             sample_rate: int = 1) -> Dict:
        """
        处理教学视频的完整流程
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录（可选，默认保存到视频文件同目录）
            sample_rate: 视频采样率（每秒采样帧数，默认1fps）
            
        Returns:
            处理结果字典
        """
        logger.info(f"开始处理教学视频: {video_path}")
        
        # 设置输出目录：默认保存到视频文件同目录
        if output_dir is None:
            video_path_obj = Path(video_path)
            video_dir = video_path_obj.parent
            video_name = video_path_obj.stem
            output_dir = str(video_dir / f"{video_name}_分析结果")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置LLM用量统计器的输出目录
        if self.usage_tracker:
            self.usage_tracker.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)
        
        try:
            # 第一阶段：基于背景减除算法提取完整PPT页面
            logger.info("1. 基于背景减除算法提取完整PPT页面...")
            logger.info("   使用MOG2背景减除器，参数优化后稳定可靠...")
            try:
                ppt_slides = self.video_processor.extract_complete_ppt_slides(
                    video_path, sample_rate
                )
                logger.info(f"   提取了 {len(ppt_slides)} 个完整PPT页面")
            except Exception as e:
                logger.error(f"背景减除算法提取PPT页面失败: {e}")
                logger.error(f"错误类型: {type(e).__name__}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                raise
            
            # 保存PPT页面图片
            if ppt_slides:
                self._save_ppt_frames(ppt_slides, output_dir)
            else:
                logger.info("   未检测到PPT页面，跳过图片保存")
            
            # 第二阶段：音频转写
            logger.info("2. 音频转写...")
            audio_transcript = self._transcribe_video_audio(video_path, output_dir)
            
            # 第三阶段：音频视频同步
            logger.info("3. 音频视频同步...")
            aligned_content = self.synchronizer.sync_audio_with_video(
                video_path, ppt_slides, audio_transcript
            )
            
            # 第四阶段：生成摘要
            logger.info("4. 生成内容摘要...")
            if audio_transcript:
                logger.info("   使用音频转写结果生成摘要...")
                # 即使PPT检测失败，也要使用音频转写结果
                if not ppt_slides and audio_transcript:
                    logger.info("   PPT检测失败，直接使用音频转写结果生成摘要...")
                    # 将音频转写结果转换为摘要格式，保持与同步器一致的结构
                    audio_summary_content = []
                    for i, segment in enumerate(audio_transcript):
                        audio_summary_content.append({
                            'timestamp': segment.get('start_time', 0),
                            'slide_content': '',  # PPT检测失败，没有幻灯片内容
                            'audio_content': {
                                'text': segment.get('text', ''),
                                'start_time': segment.get('start_time', 0),
                                'end_time': segment.get('end_time', segment.get('start_time', 0) + 10),
                                'duration': segment.get('end_time', segment.get('start_time', 0) + 10) - segment.get('start_time', 0),
                                'confidence': segment.get('confidence', 0.0)
                            },
                            'change_ratio': 0.0  # 没有场景变化检测
                        })
                    aligned_content = audio_summary_content
            else:
                logger.info("   音频转写失败，仅使用PPT内容生成摘要...")
            
            logger.info(f"   同步内容数量: {len(aligned_content)}")
            logger.info("   开始调用豆包大模型生成摘要...")
            
            # 获取PPT页面图片目录路径
            ppt_frames_dir = os.path.join(output_dir, "ppt_frames") if ppt_slides else None
            if ppt_frames_dir and os.path.exists(ppt_frames_dir):
                logger.info(f"   使用图文结合模式，PPT图片目录: {ppt_frames_dir}")
            else:
                logger.info("   使用纯文本模式生成摘要")
            
            summary = self.summary_generator.generate_comprehensive_summary(aligned_content, ppt_frames_dir)
            logger.info("   摘要生成完成")
            
            # 检查摘要是否生成成功
            if summary is None:
                logger.error("摘要生成失败，summary为None")
                raise Exception("摘要生成失败")
            
            # 保存结果
            self._save_results(summary, aligned_content, output_dir)
            
            logger.info("视频处理完成！")
            return {
                'success': True,
                'summary': summary,
                'aligned_content': aligned_content,
                'output_dir': output_dir,
                'statistics': {
                    'ppt_slides': len(ppt_slides),
                    'audio_segments': len(audio_transcript) if audio_transcript else 0
                }
            }
            
        except Exception as e:
            logger.error(f"视频处理失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'traceback': traceback.format_exc(),
                'output_dir': output_dir
            }
    
    def _transcribe_video_audio(self, video_path: str, output_dir: str) -> List[Dict]:
        """
        转写视频中的音频
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            
        Returns:
            音频转写结果
        """
        try:
            # 使用现有的音频转写功能
            audio_transcript = transcribe_audio_from_video(video_path)
            
            # 保存转写结果
            transcript_path = os.path.join(output_dir, "audio_transcript.json")
            import json
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(audio_transcript, f, ensure_ascii=False, indent=2)
            
            logger.info(f"音频转写完成，结果保存到: {transcript_path}")
            return audio_transcript
            
        except Exception as e:
            logger.error(f"音频转写失败: {e}")
            return []
    
    def _save_ppt_frames(self, ppt_slides: List[Dict], output_dir: str):
        """
        保存PPT页面图片
        
        Args:
            ppt_slides: PPT页面列表
            output_dir: 输出目录
        """
        frames_dir = os.path.join(output_dir, "ppt_frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # 创建图片信息文件
        info_file = os.path.join(frames_dir, "slides_info.txt")
        
        saved_count = 0
        for i, slide in enumerate(ppt_slides):
            timestamp = slide['timestamp']
            frame = slide['frame']
            change_ratio = slide.get('change_ratio', 0.0)
            slide_index = slide.get('slide_index', i+1)
            is_stable = slide.get('is_stable', True)
            
            # 生成文件名：slide_001_12.5s_stable.jpg
            stability_suffix = "_stable" if is_stable else "_unstable"
            filename = f"slide_{slide_index:03d}_{timestamp:.1f}s{stability_suffix}.jpg"
            filepath = os.path.join(frames_dir, filename)
            
            try:
                # 将numpy数组转换为PIL Image并保存
                if isinstance(frame, np.ndarray):
                    # 如果是BGR格式（OpenCV默认），转换为RGB
                    if len(frame.shape) == 3 and frame.shape[2] == 3:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    else:
                        frame_rgb = frame
                    
                    pil_image = Image.fromarray(frame_rgb)
                else:
                    pil_image = frame
                
                pil_image.save(filepath, quality=95)  # 高质量保存
                saved_count += 1
                
                # 记录图片信息
                with open(info_file, 'a', encoding='utf-8') as f:
                    f.write(f"幻灯片 {slide_index}: {filename}\n")
                    f.write(f"  时间戳: {timestamp:.1f}秒\n")
                    f.write(f"  变化比例: {change_ratio:.3f}\n")
                    f.write(f"  稳定性: {'稳定' if is_stable else '不稳定'}\n")
                    f.write(f"  稳定性方法: {slide.get('stability_method', 'content_based')}\n")
                    f.write(f"  内容完整性: {slide.get('content_completeness', 0.0):.2f}\n")
                    f.write(f"  文件大小: {os.path.getsize(filepath)} 字节\n")
                    
                    # 根据新的设计，文字内容由豆包多模态大模型提取，这里只记录基本信息
                    f.write(f"  页面索引: {slide.get('slide_index', '未知')}\n")
                    f.write(f"  内容完整性: {slide.get('content_completeness', 0.0):.2f}\n")
                    f.write("\n")
                    
            except Exception as e:
                logger.error(f"保存PPT页面图片失败 {filename}: {e}")
        
        logger.info(f"PPT页面图片已保存到: {frames_dir}")
        logger.info(f"成功保存 {saved_count}/{len(ppt_slides)} 个PPT页面图片")
        
        # 创建README文件说明
        readme_file = os.path.join(frames_dir, "README.md")
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write("# PPT页面图片说明\n\n")
            f.write("本目录包含从教学视频中提取的PPT页面图片。\n\n")
            f.write("## 文件命名规则\n")
            f.write("- `slide_001_12.5s.jpg`: 第1个PPT页面，出现在视频第12.5秒\n")
            f.write("- `slide_002_25.3s.jpg`: 第2个PPT页面，出现在视频第25.3秒\n\n")
            f.write("## 文件说明\n")
            f.write("- `slides_info.txt`: 详细的图片信息，包括时间戳、变化比例、文字内容等\n")
            f.write("- `README.md`: 本说明文件\n\n")
            f.write(f"## 统计信息\n")
            f.write(f"- 总PPT页面数: {len(ppt_slides)}\n")
            f.write(f"- 成功保存数: {saved_count}\n")
            f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    def _save_results(self, summary: Dict, aligned_content: List[Dict], output_dir: str):
        """
        保存处理结果
        
        Args:
            summary: 摘要结果
            aligned_content: 同步内容
            output_dir: 输出目录
        """
        # 检查summary是否为None
        if summary is None:
            logger.error("无法保存结果：summary为None")
            return
        
        # 保存摘要
        summary_path = os.path.join(output_dir, "video_summary.md")
        self.summary_generator.save_summary(summary, summary_path)
        
        # 保存同步结果
        sync_path = os.path.join(output_dir, "sync_results.json")
        self.synchronizer.save_sync_results(aligned_content, sync_path)
        
        # 保存处理报告
        print("正在保存处理结果...")
        self._save_processing_report(summary, aligned_content, output_dir)
        
        print(f"所有结果已保存到: {output_dir}")
        logger.info(f"所有结果已保存到: {output_dir}")
    
    def _save_processing_report(self, summary: Dict, aligned_content: List[Dict], output_dir: str):
        """
        保存处理报告
        
        Args:
            summary: 摘要结果
            aligned_content: 同步内容
            output_dir: 输出目录
        """
        # 检查summary是否为None
        if summary is None:
            logger.error("无法保存处理报告：summary为None")
            return
            
        report_path = os.path.join(output_dir, "processing_report.txt")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("教学视频内容分析处理报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"处理时间: {summary.get('generated_at', '未知')}\n")
            f.write(f"总PPT页面数: {summary.get('statistics', {}).get('total_slides', 0)}\n")
            f.write(f"总讲解时长: {summary.get('statistics', {}).get('total_duration', 0):.1f}秒\n")
            f.write(f"平均置信度: {summary.get('statistics', {}).get('avg_confidence', 0):.2f}\n")
            f.write(f"PPT图片保存: {output_dir}/ppt_frames/\n\n")
            
            f.write("关键要点:\n")
            for i, point in enumerate(summary.get('key_points', []), 1):
                f.write(f"{i}. {point}\n")
            
            f.write("\n学习建议:\n")
            for suggestion in summary.get('learning_suggestions', []):
                f.write(f"- {suggestion}\n")
        
        logger.info(f"处理报告已保存到: {report_path}")

def main():
    """主函数"""
    # 简化命令行参数，主要支持直接传入视频文件路径
    if len(sys.argv) < 2:
        print("使用方法: python video_main.py <视频文件路径> [选项]")
        print("示例: python video_main.py lecture.mp4")
        print("示例: python video_main.py lecture.mp4 --sample-rate 5")
        print("注意: 使用背景减除算法进行PPT页面检测，参数已优化")
        return
    
    video_path = sys.argv[1]
    
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return
    
    # 解析可选参数
    sample_rate = 3
    
    # 查找参数值
    for i, arg in enumerate(sys.argv):
        if arg == "--sample-rate" and i + 1 < len(sys.argv):
            try:
                sample_rate = int(sys.argv[i + 1])
            except ValueError:
                logger.warning("采样率参数无效，使用默认值3")
    
    logger.info(f"处理视频: {video_path}")
    logger.info(f"采样率: {sample_rate}")
    logger.info("使用背景减除算法进行PPT页面检测")
    
    # 初始化分析器
    print("正在初始化视频分析器...")
    analyzer = VideoContentAnalyzer()
    print("视频分析器初始化完成！")
    
    # 处理视频（输出目录为None，将自动保存到视频文件同目录）
    print("开始处理视频...")
    result = analyzer.process_teaching_video(
        video_path=video_path,
        output_dir=None,  # 自动保存到视频文件同目录
        sample_rate=sample_rate
    )
    
    if result['success']:
        logger.info("视频处理成功完成！")
        logger.info(f"输出目录: {result['output_dir']}")
        logger.info(f"统计信息: {result['statistics']}")
        
        # 生成大模型用量统计报告
        try:
            from util.llm_usage_tracker import get_global_tracker
            # 获取全局统计器并设置输出目录为视频分析结果目录
            tracker = get_global_tracker(result['output_dir'])
            tracker.print_summary()
            usage_report_path = tracker.save_usage_report()
            print(f"大模型用量报告已保存到视频分析结果目录: {usage_report_path}")
        except ImportError:
            print("大模型用量统计功能未启用")
        
        print(f"\n处理完成！结果已保存到: {result['output_dir']}")
    else:
        error_msg = result.get('error', '未知错误')
        error_type = result.get('error_type', 'Unknown')
        traceback_info = result.get('traceback', '')
        
        logger.error(f"视频处理失败: {error_msg}")
        logger.error(f"错误类型: {error_type}")
        if traceback_info:
            logger.error(f"详细错误信息: {traceback_info}")
        
        print(f"\n处理失败: {error_msg}")
        print(f"错误类型: {error_type}")
        if traceback_info:
            print(f"详细错误信息: {traceback_info}")

if __name__ == "__main__":
    main() 
