def chunk_content(text: str, max_chars: int = 10000) -> list:
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = []
    current_length = 0
    for para in paragraphs:
        if not para.strip():
            continue
        para_length = len(para)
        if current_length + para_length > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(para)
        current_length += para_length
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks 