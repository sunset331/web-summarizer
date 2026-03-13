"""
大模型用量统计工具
支持讯飞语音转文字和豆包多模态大模型的token统计
"""

import json
import os
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class LLMUsageRecord:
    """大模型使用记录"""
    timestamp: str
    model_type: str  # 'xunfei_asr' 或 'doubao_multimodal'
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration: float  # API调用耗时（秒）
    success: bool
    error_message: str = ""
    metadata: Dict = None

class LLMUsageTracker:
    """大模型用量统计器"""
    
    def __init__(self, output_dir: str = None):
        """
        初始化统计器
        
        Args:
            output_dir: 输出目录，默认为当前目录
        """
        self.output_dir = output_dir or os.getcwd()
        self.usage_records: List[LLMUsageRecord] = []
        self.session_start_time = datetime.now()
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"大模型用量统计器初始化完成，输出目录: {self.output_dir}")
    
    def record_xunfei_asr_usage(self, 
                               model_name: str = "xunfei_long_asr",
                               input_tokens: int = 0,
                               output_tokens: int = 0,
                               duration: float = 0.0,
                               audio_duration: float = 0.0,
                               success: bool = True,
                               error_message: str = "",
                               metadata: Dict = None) -> None:
        """
        记录讯飞语音转文字使用情况
        
        Args:
            model_name: 模型名称
            input_tokens: 输入token数（字符数）
            output_tokens: 输出token数（字符数）
            duration: API调用耗时
            audio_duration: 音频时长（秒）
            success: 是否成功
            error_message: 错误信息
            metadata: 额外信息
        """
        # 确保metadata包含音频时长信息
        if metadata is None:
            metadata = {}
        metadata['audio_duration'] = audio_duration
        metadata['token_source'] = 'actual_transcription'  # 讯飞ASR按实际转写字符数
        
        record = LLMUsageRecord(
            timestamp=datetime.now().isoformat(),
            model_type="xunfei_asr",
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            duration=duration,
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        self.usage_records.append(record)
        logger.debug(f"记录讯飞ASR使用: 音频时长 {audio_duration:.1f}s, 字符数 {record.total_tokens}, API耗时: {duration:.2f}s")
    
    def record_doubao_multimodal_usage(self,
                                      model_name: str = "doubao-seed-1-6-250615",
                                      input_tokens: int = 0,
                                      output_tokens: int = 0,
                                      duration: float = 0.0,
                                      success: bool = True,
                                      error_message: str = "",
                                      metadata: Dict = None) -> None:
        """
        记录豆包多模态大模型使用情况
        
        Args:
            model_name: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数
            duration: API调用耗时
            success: 是否成功
            error_message: 错误信息
            metadata: 额外信息
        """
        # 确保metadata包含token来源信息
        if metadata is None:
            metadata = {}
        metadata['token_source'] = 'api_response'  # 豆包API返回的token数
        
        record = LLMUsageRecord(
            timestamp=datetime.now().isoformat(),
            model_type="doubao_multimodal",
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            duration=duration,
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        self.usage_records.append(record)
        logger.debug(f"记录豆包多模态使用: 输入{input_tokens} tokens, 输出{output_tokens} tokens, 总{record.total_tokens} tokens, 耗时: {duration:.2f}s")
    
    def estimate_tokens(self, text: str, model_type: str) -> int:
        """
        估算文本的token数量
        
        Args:
            text: 输入文本
            model_type: 模型类型
            
        Returns:
            估算的token数量
        """
        if not text:
            return 0
        
        # 简单的token估算（中文约1.5字符/token，英文约0.75字符/token）
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = len(text) - chinese_chars
        
        if model_type == "xunfei_asr":
            # 讯飞ASR通常按字符计算
            return len(text)
        else:
            # 豆包多模态按token计算
            return int(chinese_chars * 1.5 + english_chars * 0.75)
    
    def get_session_summary(self) -> Dict:
        """
        获取当前会话的统计摘要
        
        Returns:
            统计摘要字典
        """
        if not self.usage_records:
            return {
                "session_duration": 0,
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost": 0,
                "success_rate": 0,
                "model_breakdown": {}
            }
        
        session_duration = (datetime.now() - self.session_start_time).total_seconds()
        total_calls = len(self.usage_records)
        total_tokens = sum(record.total_tokens for record in self.usage_records)
        successful_calls = sum(1 for record in self.usage_records if record.success)
        success_rate = successful_calls / total_calls if total_calls > 0 else 0
        
        # 按模型类型分组统计
        model_breakdown = {}
        for record in self.usage_records:
            model_key = f"{record.model_type}_{record.model_name}"
            if model_key not in model_breakdown:
                model_breakdown[model_key] = {
                    "calls": 0,
                    "tokens": 0,
                    "duration": 0,
                    "success_count": 0
                }
            
            model_breakdown[model_key]["calls"] += 1
            model_breakdown[model_key]["tokens"] += record.total_tokens
            model_breakdown[model_key]["duration"] += record.duration
            if record.success:
                model_breakdown[model_key]["success_count"] += 1
        
        # 估算成本（仅供参考）
        total_cost = self._estimate_cost()
        
        return {
            "session_duration": session_duration,
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "success_rate": success_rate,
            "model_breakdown": model_breakdown,
            "session_start": self.session_start_time.isoformat(),
            "session_end": datetime.now().isoformat()
        }
    
    def _estimate_cost(self) -> float:
        """
        估算总成本（仅供参考）
        
        Returns:
            估算的成本（元）
        """
        total_cost = 0.0
        
        for record in self.usage_records:
            if record.model_type == "xunfei_asr":
                # 讯飞ASR按时长计费
                # 从metadata中获取音频时长，如果没有则使用duration作为估算
                audio_duration = record.metadata.get('audio_duration', record.duration) if record.metadata else record.duration
                # 讯飞ASR价格：约0.3元/小时，即0.000083元/秒
                cost = audio_duration * 0.000083
            elif record.model_type == "doubao_multimodal":
                # 豆包多模态按token计费
                # 假设输入0.001元/1K tokens，输出0.002元/1K tokens
                input_cost = record.input_tokens / 1000 * 0.001
                output_cost = record.output_tokens / 1000 * 0.002
                cost = input_cost + output_cost
            else:
                cost = 0
            
            total_cost += cost
        
        return total_cost
    
    def save_usage_report(self, filename: str = None) -> str:
        """
        保存使用报告
        
        Args:
            filename: 文件名，默认为自动生成
            
        Returns:
            保存的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"llm_usage_report_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # 准备报告数据
        report_data = {
            "summary": self.get_session_summary(),
            "detailed_records": [asdict(record) for record in self.usage_records]
        }
        
        # 保存JSON报告
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        # 生成Markdown报告
        md_filepath = filepath.replace('.json', '.md')
        self._generate_markdown_report(report_data, md_filepath)
        
        logger.info(f"使用报告已保存: {filepath}")
        logger.info(f"Markdown报告已保存: {md_filepath}")
        
        return filepath
    
    def _generate_markdown_report(self, report_data: Dict, filepath: str) -> None:
        """
        生成Markdown格式的报告
        
        Args:
            report_data: 报告数据
            filepath: 输出文件路径
        """
        summary = report_data["summary"]
        
        markdown = f"""# 大模型使用统计报告

## 会话概览
- **会话开始时间**: {summary.get('session_start', '未知')}
- **会话结束时间**: {summary.get('session_end', '未知')}
- **会话持续时间**: {summary.get('session_duration', 0):.1f}秒
- **总调用次数**: {summary.get('total_calls', 0)}
- **总Token数**: {summary.get('total_tokens', 0):,}
- **成功率**: {summary.get('success_rate', 0):.1%}
- **估算成本**: ¥{summary.get('total_cost', 0):.4f}

## 模型使用详情

"""
        
        for model_key, stats in summary.get('model_breakdown', {}).items():
            model_type, model_name = model_key.split('_', 1)
            success_rate = stats['success_count'] / stats['calls'] if stats['calls'] > 0 else 0
            
            markdown += f"""### {model_name} ({model_type})
- **调用次数**: {stats['calls']}
- **总Token数**: {stats['tokens']:,}
- **总耗时**: {stats['duration']:.2f}秒
- **成功率**: {success_rate:.1%}
- **平均耗时**: {stats['duration']/stats['calls']:.2f}秒/次

"""
        
        markdown += """## 详细记录

| 时间 | 模型类型 | 模型名称 | 输入Token | 输出Token | 总Token | 耗时(秒) | 状态 | Token来源 |
|------|----------|----------|-----------|-----------|---------|----------|------|-----------|
"""
        
        for record in report_data["detailed_records"]:
            status = "成功" if record['success'] else "失败"
            token_source = record.get('metadata', {}).get('token_source', 'estimated')
            markdown += f"| {record['timestamp'][:19]} | {record['model_type']} | {record['model_name']} | {record['input_tokens']:,} | {record['output_tokens']:,} | {record['total_tokens']:,} | {record['duration']:.2f} | {status} | {token_source} |\n"
        
        markdown += f"""

## 使用建议
- 监控API调用频率，避免超出限制
- 优化输入内容，减少不必要的token消耗
- 定期检查使用报告，控制成本

## 计费方式说明
- **讯飞ASR**: 按音频时长计费，约0.3元/小时
- **豆包多模态**: 按token计费，输入约0.001元/1K tokens，输出约0.002元/1K tokens

## Token统计说明
- **api_response**: 来自API响应的真实token数（豆包多模态）
- **actual_transcription**: 基于实际转写结果的字符数（讯飞ASR）
- **estimated**: 基于文本长度的估算token数（仅供参考）

> **注意**: 讯飞ASR按音频时长计费，token数仅用于统计转写字符数。豆包多模态按token计费，以API返回的实际token数为准。

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown)
    
    def print_summary(self) -> None:
        """打印当前会话摘要"""
        summary = self.get_session_summary()
        
        print("\n" + "="*50)
        print("大模型使用统计摘要")
        print("="*50)
        print(f"会话持续时间: {summary['session_duration']:.1f}秒")
        print(f"总调用次数: {summary['total_calls']}")
        print(f"总Token数: {summary['total_tokens']:,}")
        print(f"成功率: {summary['success_rate']:.1%}")
        print(f"估算成本: ¥{summary['total_cost']:.4f}")
        
        if summary['model_breakdown']:
            print("\n模型使用详情:")
            for model_key, stats in summary['model_breakdown'].items():
                model_type, model_name = model_key.split('_', 1)
                success_rate = stats['success_count'] / stats['calls'] if stats['calls'] > 0 else 0
                if model_type == "xunfei_asr":
                    print(f"  {model_name}: {stats['calls']}次调用, {stats['tokens']:,}字符, {stats['duration']:.1f}秒音频, {success_rate:.1%}成功率")
                else:
                    print(f"  {model_name}: {stats['calls']}次调用, {stats['tokens']:,}tokens, {success_rate:.1%}成功率")
        
        print("="*50)

# 全局统计器实例
_global_tracker = None

def get_global_tracker(output_dir: str = None) -> LLMUsageTracker:
    """
    获取全局统计器实例
    
    Args:
        output_dir: 输出目录
        
    Returns:
        全局统计器实例
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LLMUsageTracker(output_dir)
    elif output_dir is not None:
        # 如果已经存在实例但传入了新的输出目录，则更新输出目录
        _global_tracker.output_dir = output_dir
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    return _global_tracker

def record_xunfei_usage(**kwargs) -> None:
    """记录讯飞使用情况的便捷函数"""
    tracker = get_global_tracker()
    tracker.record_xunfei_asr_usage(**kwargs)

def record_doubao_usage(**kwargs) -> None:
    """记录豆包使用情况的便捷函数"""
    tracker = get_global_tracker()
    tracker.record_doubao_multimodal_usage(**kwargs)

def save_and_print_report() -> str:
    """保存并打印报告的便捷函数"""
    tracker = get_global_tracker()
    tracker.print_summary()
    return tracker.save_usage_report() 