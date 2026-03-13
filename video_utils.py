import cv2
import os
import time
import imutils
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class VideoProcessor:
    """视频处理器类 - 使用背景减除算法检测PPT页面"""
    
    def __init__(self):
        """初始化视频处理器"""
        # 背景减除算法参数
        self.frame_rate = 5                   # 每秒处理的帧数
        self.warmup = 5                       # 初始跳过的帧数
        self.fgbg_history = 30                # 背景对象中的帧数
        self.var_threshold = 16               # 像素和模型之间的平方马氏距离阈值
        self.detect_shadows = False           # 是否检测阴影
        self.min_percent = 1                  # 检测运动停止的最小差异百分比
        self.max_percent = 10.5               # 检测帧仍在运动的最大差异百分比
        
        logger.info("视频处理器初始化完成")
        logger.info(f"背景减除参数: 帧率={self.frame_rate}, 最小差异={self.min_percent}%, 最大差异={self.max_percent}%")
    
    def extract_complete_ppt_slides(self, video_path: str, sample_rate: int = 1) -> List[Dict]:
        """
        提取完整的PPT页面（基于背景减除算法）
        
        Args:
            video_path: 视频文件路径
            sample_rate: 采样率（每秒采样帧数，此参数在此算法中不使用）
            
        Returns:
            PPT页面列表
        """
        logger.info(f"开始使用背景减除算法提取PPT页面")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 使用背景减除算法检测PPT页面
        ppt_slides = self._detect_ppt_slides_by_background_subtraction(video_path)
        
        logger.info(f"检测到 {len(ppt_slides)} 个PPT页面")
        return ppt_slides
    
    def _detect_ppt_slides_by_background_subtraction(self, video_path: str) -> List[Dict]:
        """
        基于背景减除算法检测PPT页面切换
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            PPT页面列表
        """
        logger.info("开始基于背景减除算法检测PPT页面切换...")
        
        # 初始化背景减除器对象
        fgbg = cv2.createBackgroundSubtractorMOG2(
            history=self.fgbg_history, 
            varThreshold=self.var_threshold,
            detectShadows=self.detect_shadows
        )

        captured = False
        start_time = time.time()
        (W, H) = (None, None)

        screenshots_count = 0
        total_frames = 0
        ppt_slides = []
        
        logger.info(f"开始处理视频: {video_path}")
        logger.info(f"参数设置: 帧率={self.frame_rate}, 最小差异={self.min_percent}%, 最大差异={self.max_percent}%")
        
        # 打开视频文件
        vs = cv2.VideoCapture(video_path)
        if not vs.isOpened():
            raise Exception(f'无法打开文件 {video_path}')

        total_video_frames = vs.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = vs.get(cv2.CAP_PROP_FPS)
        frame_time = 0
        frame_count = 0
        
        logger.info(f"视频信息: 总帧数={total_video_frames}, FPS={fps}")

        # 循环处理视频帧
        while True:
            # 从视频中抓取一帧
            vs.set(cv2.CAP_PROP_POS_MSEC, frame_time * 1000)    # 移动到时间戳
            frame_time += 1/self.frame_rate

            (ret, frame) = vs.read()
            # 如果帧为None，则已到达视频文件末尾
            if not ret or frame is None:
                break

            frame_count += 1
            total_frames += 1
            
            # 显示进度
            if total_frames % 10 == 0:
                logger.info(f"处理进度: 第 {total_frames} 帧, 时间: {frame_time:.1f}s")
            
            orig = frame.copy()  # 克隆原始帧
            frame = imutils.resize(frame, width=600)  # 调整帧大小
            mask = fgbg.apply(frame)  # 应用背景减除器

            # 如果宽度和高度为空，获取空间维度
            if W is None or H is None:
                (H, W) = mask.shape[:2]

            # 计算掩码中"前景"的百分比
            p_diff = (cv2.countNonZero(mask) / float(W * H)) * 100

            # 如果 p_diff 小于 MIN_PERCENT%，则运动已停止，因此捕获帧
            if p_diff < self.min_percent and not captured and frame_count > self.warmup:
                captured = True
                
                # 创建PPT页面信息
                slide_info = {
                    'slide_index': screenshots_count + 1,
                    'timestamp': frame_time,
                    'frame': orig,  # 保存原始帧
                    'start_time': frame_time,
                    'end_time': frame_time,  # 稍后会更新
                    'duration': 0,  # 稍后会计算
                    'change_ratio': p_diff,
                    'is_stable': True,
                    'stability_method': 'background_subtraction',
                    'content_completeness': 1.0,
                    'frame_index': frame_count,
                    'foreground_percentage': p_diff
                }
                
                ppt_slides.append(slide_info)
                screenshots_count += 1
                
                logger.info(f"检测到第 {screenshots_count} 个PPT页面: 时间戳 {frame_time:.1f}s, 差异百分比: {p_diff:.2f}%")

            # 否则，场景正在变化或我们仍在预热模式
            # 等待场景稳定或完成背景模型构建
            elif captured and p_diff >= self.max_percent:
                captured = False
                logger.info(f"检测到运动变化 (差异百分比: {p_diff:.2f}%), 重置捕获状态")
        
        vs.release()
        
        # 更新每个页面的结束时间和持续时间
        for i in range(len(ppt_slides)):
            if i < len(ppt_slides) - 1:
                ppt_slides[i]['end_time'] = ppt_slides[i + 1]['start_time']
                ppt_slides[i]['duration'] = ppt_slides[i]['end_time'] - ppt_slides[i]['start_time']
            else:
                # 最后一个页面，使用视频结束时间
                ppt_slides[i]['end_time'] = frame_time
                ppt_slides[i]['duration'] = ppt_slides[i]['end_time'] - ppt_slides[i]['start_time']
        
        logger.info(f"背景减除算法处理完成！")
        logger.info(f"总耗时: {time.time()-start_time:.2f}秒")
        logger.info(f"处理帧数: {total_frames}")
        logger.info(f"检测到 {screenshots_count} 个PPT页面")
        
        return ppt_slides 