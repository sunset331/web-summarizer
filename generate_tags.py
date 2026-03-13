from openai import OpenAI

def generate_content_tags(text: str, api_key: str = "", model_name: str = "") -> dict:
    """
    使用火山引擎豆包大模型生成内容分类标签。
    返回包含主题词和用户潜在记录目的的字典。
    """
    # 从配置文件获取豆包API配置
    from util.config_manager import get_doubao_config
    doubao_config = get_doubao_config()
    api_key = api_key or doubao_config.get('api_key')
    base_url = doubao_config.get('base_url')
    model = model_name or doubao_config.get('model')
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的内容分析专家。请分析给定内容并生成两类标签：1. 内容主题词（如：北京、旅游、美食、科技等）2. 用户潜在记录目的（如：旅行种草、学习参考、工作备忘、生活记录等）。请以JSON格式返回结果。"},
                {"role": "user", "content": f"请分析以下内容并生成标签，格式要求：\n{{\n  \"content_tags\": [\"标签1\", \"标签2\", \"标签3\"],\n  \"user_purpose\": [\"目的1\", \"目的2\"]\n}}\n\n内容：\n{text[:3000]}"}
            ],
            temperature=0.3,
            max_tokens=500,
            timeout=30
        )
        
        content = response.choices[0].message.content
        if content:
            # 尝试解析JSON响应
            import json
            try:
                # 提取JSON部分
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = content[start_idx:end_idx]
                    result = json.loads(json_str)
                    return {
                        "content_tags": result.get("content_tags", []),
                        "user_purpose": result.get("user_purpose", [])
                    }
            except json.JSONDecodeError:
                pass
            
            # 如果JSON解析失败，尝试手动提取标签
            return extract_tags_from_text(content)
        else:
            return {"content_tags": [], "user_purpose": []}
            
    except Exception as e:
        print(f"[ERROR] 标签生成失败: {str(e)}")
        return {"content_tags": [], "user_purpose": []}

def extract_tags_from_text(text: str) -> dict:
    """
    从文本中手动提取标签（备用方案）
    """
    content_tags = []
    user_purpose = []
    
    # 常见主题词
    common_topics = [
        "旅游", "美食", "科技", "教育", "健康", "时尚", "娱乐", "体育", "财经", "政治",
        "北京", "上海", "广州", "深圳", "杭州", "成都", "西安", "南京", "武汉", "重庆",
        "攻略", "评测", "教程", "新闻", "观点", "经验", "分享", "推荐", "对比", "分析"
    ]
    
    # 常见用户目的
    common_purposes = [
        "旅行种草", "学习参考", "工作备忘", "生活记录", "购物参考", "知识积累",
        "决策参考", "兴趣收藏", "研究资料", "个人成长", "娱乐消遣", "社交分享"
    ]
    
    # 检查内容中是否包含这些关键词
    for topic in common_topics:
        if topic in text:
            content_tags.append(topic)
    
    # 根据内容特征推断用户目的
    if any(word in text for word in ["旅游", "攻略", "景点", "酒店", "机票"]):
        user_purpose.append("旅行种草")
    if any(word in text for word in ["教程", "学习", "知识", "技能"]):
        user_purpose.append("学习参考")
    if any(word in text for word in ["工作", "项目", "管理", "效率"]):
        user_purpose.append("工作备忘")
    if any(word in text for word in ["美食", "购物", "推荐", "评测"]):
        user_purpose.append("购物参考")
    
    # 如果没有匹配到特定目的，添加通用目的
    if not user_purpose:
        user_purpose.append("知识积累")
    
    return {
        "content_tags": content_tags[:5],  # 限制标签数量
        "user_purpose": user_purpose[:3]   # 限制目的数量
    } 