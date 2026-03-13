import os
import base64
from typing import List
from openai import OpenAI
from util._save_raw_text import image_to_base64

def generate_multimodal_summary(text: str, image_paths: List[str], 
                              api_key: str = "", model: str = "") -> str:
    """使用豆包多模态API生成会议摘要"""
    try:
        print(f"[INFO] 开始多模态会议摘要，文本长度: {len(text)}")
        print(f"[INFO] 图片路径数量: {len(image_paths)}")
        
        # 从配置文件获取豆包API配置
        from util.config_manager import get_doubao_config
        doubao_config = get_doubao_config()
        api_key = api_key or doubao_config.get('api_key')
        base_url = doubao_config.get('base_url')
        model = model or doubao_config.get('model')
        
        # 处理图片，转换为Base64编码
        image_contents = []
        if image_paths:
            print(f"开始处理 {len(image_paths)} 张图片...")
            for i, img_path in enumerate(image_paths):
                if os.path.exists(img_path):
                    print(f"处理图片 {i+1}/{len(image_paths)}: {os.path.basename(img_path)}")
                    base64_data = image_to_base64(img_path)
                    if base64_data:
                        image_contents.append(base64_data)
                        print(f"图片处理成功: {os.path.basename(img_path)}")
                    else:
                        print(f"图片处理失败: {os.path.basename(img_path)}")
                else:
                    print(f"图片文件不存在: {img_path}")
        
        print(f"[INFO] 开始构造AI请求，图片数量: {len(image_contents)}")
        
        # 构造多模态消息内容
        content = []
        user_prompt = f"""
        你是一个专业的会议记录助手，请根据提供的会议音频转写文字和相关图片，生成一份详细的会议摘要。

        【会议摘要要求】
        1. 会议主题和主要议题
        2. 关键讨论内容和观点
        3. 重要决策和行动项
        4. 图片内容分析（如果有图片）
        5. 图片与会议内容的对应关系

        【输出格式】
        # 会议摘要

        ## 会议主题
        [会议的主要主题]

        ## 主要议题
        1. [议题1]
        2. [议题2]
        ...

        ## 关键讨论内容
        [重要讨论的详细内容]

        ## 重要决策
        - [决策1]
        - [决策2]
        ...

        ## 行动项
        - [ ] [行动项1]
        - [ ] [行动项2]
        ...

        ## 图片内容分析（如果有）
        [分析图片中的图表、文档等内容，以及与会议讨论的关联]

        会议记录内容如下：
        {text}
        """
        
        content.append({"type": "text", "text": user_prompt})
        
        # 添加图片内容
        max_images = 20
        for i, base64_data in enumerate(image_contents[:max_images]):
            content.append({"type": "image_url", "image_url": {"url": base64_data}})
        
        print(f"[INFO] 实际传递图片数量: {len(content) - 1}")
        
        # 使用OpenAI客户端调用，参考summary_xhs.py
        client = OpenAI(api_key=api_key, base_url=base_url)
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=0.3,
                max_tokens=20000,
                timeout=120
            )
            summary = completion.choices[0].message.content
            print("豆包大模型多模态会议摘要生成成功")
            return summary.strip() if summary else "摘要生成失败：API返回空内容"
        except Exception as e:
            print(f"[ERROR] 豆包大模型多模态API调用失败: {str(e)}")
            return fallback_text_summary(text)
    except Exception as e:
        print(f"[ERROR] 豆包大模型多模态API调用失败: {str(e)}")
        return fallback_text_summary(text)

def fallback_text_summary(text: str) -> str:
    """文本模式备用方案"""
    try:
        # 从配置文件获取豆包API配置
        from util.config_manager import get_doubao_config
        doubao_config = get_doubao_config()
        api_key = doubao_config.get('api_key')
        base_url = doubao_config.get('base_url')
        model = doubao_config.get('model')
        client = OpenAI(api_key=api_key, base_url=base_url)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的会议记录助手。请根据提供的会议文字记录，生成一份详细的会议摘要。使用中文输出结果。"},
                {"role": "user", "content": f"请为以下会议记录生成详细摘要：\n\n{text}"}
            ],
            temperature=0.3,
            max_tokens=2000,
            timeout=60
        )
        summary = completion.choices[0].message.content
        if summary:
            return summary.strip()
        else:
            return "摘要生成失败：API返回空内容"
    except Exception as e:
        print(f"[ERROR] 文本模式也失败: {str(e)}")
        return simple_text_summary(text)

def simple_text_summary(text: str) -> str:
    """简单的文本摘要，不依赖外部API"""
    try:
        lines = text.split('\n')
        content_lines = [line.strip() for line in lines if len(line.strip()) > 10]
        if not content_lines:
            return "内容为空，无法生成摘要"
        summary_lines = content_lines[:3]
        summary = "\n\n".join(summary_lines)
        if len(summary) > 500:
            summary = summary[:500] + "..."
        return f"# 会议摘要\n\n{summary}\n\n*注：这是基于文本内容的简单摘要，如需更详细的多模态分析，请配置正确的API Key。*"
    except Exception as e:
        return f"摘要生成失败：{str(e)}"

if __name__ == "__main__":
    # 测试函数
    test_text = "这是一个测试会议记录。"
    test_images = []
    
    summary = generate_multimodal_summary(test_text, test_images)
    print("测试摘要:", summary) 