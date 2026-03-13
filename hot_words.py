from textrank4zh import TextRank4Keyword

def extract_keywords_for_hotword(text, top_k=20):
    """
    使用TextRank算法提取关键词，生成用于语音识别的热词字符串
    :param text: 需要提取关键词的文本（标题+简介）
    :param top_k: 返回的关键词数量上限
    :return: 一个以'|'分隔的热词字符串, e.g., "关键词1|关键词2"
    """
    if not text or not isinstance(text, str):
        return ""

    print(f"[INFO] 开始生成热词，文本长度: {len(text)} 字符")

    # 定义允许的词性，主要关注名词和专有名词
    allowed_pos = ('n', 'nr', 'ns', 'nt', 'nz', 'eng')

    # 使用TextRank算法提取关键词，并结合词性标注
    tr4w = TextRank4Keyword(allow_speech_tags=allowed_pos)
    tr4w.analyze(text=text, lower=True, window=2)

    keywords = []
    # 获取最重要的top_k个词
    for item in tr4w.get_keywords(top_k, word_min_len=2):
        keywords.append(item.word)

    # 过滤掉单字和纯数字的词
    filtered_keywords = [kw for kw in keywords if not kw.isdigit() and len(kw) > 1]
    
    print(f"[INFO] TextRank算法提取到热词: {filtered_keywords}")
    
    return "|".join(filtered_keywords)

if __name__ == '__main__':
    # 测试函数
    sample_title = "早咖啡：淘宝闪购日订单超8000万，韩国化妆品出口创新高"
    sample_description = """
    本周节目由图拉斯冠名播出，图拉斯 O3Air 支点壳，定格夏夜，轻盈随行。

本期早咖啡为你带来与日常生活息息相关的商业科技动态，你将会听到：

淘宝闪购日订单超过 8000 万
韩国上半年化妆品出口额创新高
梦龙冰激淋公司正式开始独立运营
《F1》成为苹果票房最高的电影
本期还有关于小米、三大运营商、TikTok、富士康和大众的新动态，欢迎收听！
    """
    
    # 合并标题和简介
    sample_text = f"{sample_title} {sample_description}"
    
    print("=== 测试TextRank热词生成 ===")
    # 测试TextRank算法
    hotword_string = extract_keywords_for_hotword(sample_text)
    print("\n[+] 生成的热词字符串:")
    print(hotword_string) 