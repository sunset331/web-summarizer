"""
Web 服务调用的音频 / 视频 / 会议处理管线（与 audio_main、video_main、meeting_main 逻辑对齐，输出写入指定目录）。
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import zipfile
from typing import Callable, Optional

ProgressCb = Optional[Callable[[int, str], None]]


def _p(cb: ProgressCb, pct: int, msg: str) -> None:
    if cb:
        try:
            cb(max(0, min(100, pct)), msg)
        except Exception:
            pass


def run_audio_url_to_dir(url: str, out_dir: str, cb: ProgressCb = None) -> str:
    """喜马拉雅 / 小宇宙 / 网易云 音频链接：下载、转写、摘要。返回生成的 summary.md 路径。"""
    from util.audio_utils import download_audio, preprocess_order_result, xunfei_asr_long, convert_to_wav
    from util.config_manager import get_xunfei_config
    from util.generate_summary import generate_audio_summary
    from util.hot_words import extract_keywords_for_hotword
    from xiaoyuzhoufm import XiaoyuzhouFMParser
    from ximalaya import XimalayaParser
    from wangyiyun import WangyiyunParser

    os.makedirs(out_dir, exist_ok=True)
    xf = get_xunfei_config()
    appid, secret = xf.get("appid"), xf.get("secret")

    _p(cb, 5, "Detecting audio platform…")
    url_l = url.strip()
    if "xiaoyuzhoufm.com" in url_l:
        parser = XiaoyuzhouFMParser()
        platform = "xiaoyuzhoufm"
    elif "ximalaya.com" in url_l:
        parser = XimalayaParser()
        platform = "ximalaya"
    elif "music.163.com" in url_l:
        parser = WangyiyunParser()
        platform = "wangyiyun"
    else:
        raise ValueError("Unsupported audio URL (need ximalaya / xiaoyuzhoufm / music.163.com)")

    _p(cb, 12, "Fetching audio metadata…")
    info = parser.get_audio_info(url_l)
    title = (info.get("title") or "audio")[:80]
    safe_prefix = "".join(c if c.isalnum() or c in "_- " else "_" for c in title).strip().replace(" ", "_")[:60]
    prefix = f"{platform}_{safe_prefix}"

    _p(cb, 25, "Downloading audio…")
    audio_ext = os.path.splitext(info["audio_url"].split("/")[-1].split("?")[0])[1] or ".m4a"
    audio_filename = f"{prefix}_origin{audio_ext}"
    audio_path = os.path.join(out_dir, audio_filename)
    download_audio(info["audio_url"], out_dir, filename=audio_filename)

    _p(cb, 40, "Converting to WAV…")
    wav_path = os.path.join(out_dir, f"{prefix}_16k.wav")
    convert_to_wav(audio_path, wav_path)
    try:
        os.remove(audio_path)
    except OSError:
        pass

    combined = f"{info.get('title', '')} {info.get('description', '')}"
    hot_words = extract_keywords_for_hotword(combined)

    _p(cb, 55, "Transcribing (iFlytek)…")
    _, result_json = xunfei_asr_long(wav_path, appid, secret, hot_word=hot_words)
    result_json = preprocess_order_result(result_json)
    json_path = os.path.join(out_dir, f"{prefix}_raw.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_json, f, ensure_ascii=False, indent=2)

    timestamped_texts: list[str] = []
    if "content" in result_json and "orderResult" in result_json["content"]:
        order_result = result_json["content"]["orderResult"]
        if "lattice" in order_result:
            for lattice_item in order_result["lattice"]:
                if "json_1best" not in lattice_item:
                    continue
                json_1best = lattice_item["json_1best"]
                if "st" not in json_1best or "rt" not in json_1best["st"]:
                    continue
                st = json_1best["st"]
                bg, ed = st.get("bg", 0), st.get("ed", 0)
                text_content = ""
                if "rt" in st and isinstance(st["rt"], list):
                    for rt_item in st["rt"]:
                        if "ws" not in rt_item or not isinstance(rt_item["ws"], list):
                            continue
                        for ws_item in rt_item["ws"]:
                            if "cw" not in ws_item or not isinstance(ws_item["cw"], list):
                                continue
                            text_content += "".join(
                                cw_item.get("w", "") for cw_item in ws_item["cw"]
                            )
                if text_content.strip():
                    start_seconds, end_seconds = int(bg) / 1000.0, int(ed) / 1000.0
                    if start_seconds < 60:
                        start_time = f"{start_seconds:.1f}s"
                    else:
                        start_time = f"{int(start_seconds // 60)}m{int(start_seconds % 60)}s"
                    if end_seconds < 60:
                        end_time = f"{end_seconds:.1f}s"
                    else:
                        end_time = f"{int(end_seconds // 60)}m{int(end_seconds % 60)}s"
                    timestamped_texts.append(f"{text_content} [time: {start_time}-{end_time}]")

    timestamped_text = "\n".join(timestamped_texts)
    text_path = os.path.join(out_dir, f"{prefix}_transcript.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(timestamped_text)

    pure_text = "\n".join(
        t.split(" [time:")[0] for t in timestamped_texts if t.strip()
    )
    summary_path = os.path.join(out_dir, f"{prefix}_summary.md")
    if not pure_text.strip():
        raise RuntimeError("No transcript text from ASR")

    _p(cb, 80, "Generating summary (Doubao)…")
    summary = generate_audio_summary(timestamped_text, "", "")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    _p(cb, 100, "Audio pipeline done")
    return summary_path


def run_video_file_to_dir(
    video_path: str, out_dir: str, sample_rate: int = 3, cb: ProgressCb = None
) -> str:
    """教学视频分析：输出目录内含 video_summary.md 等。"""
    from video_main import VideoContentAnalyzer

    os.makedirs(out_dir, exist_ok=True)
    _p(cb, 5, "Initializing video analyzer…")
    analyzer = VideoContentAnalyzer()
    _p(cb, 15, "Processing video (PPT + ASR + sync), may take long…")
    result = analyzer.process_teaching_video(
        video_path=video_path, output_dir=out_dir, sample_rate=sample_rate
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "Video processing failed")
    summary_md = os.path.join(out_dir, "video_summary.md")
    if not os.path.isfile(summary_md):
        raise RuntimeError("video_summary.md not found after processing")
    _p(cb, 100, "Video pipeline done")
    return summary_md


def run_meeting_zip_to_dir(
    zip_path: str, work_dir: str, understand_images: bool = True, cb: ProgressCb = None
) -> str:
    """
    解压会议资源包到 work_dir/meeting_in，要求 zip 内为「同一文件夹下的音频 + 截图」扁平或可单层目录。
    """
    from meeting_main import MeetingTranscriber

    bundle = os.path.join(work_dir, "meeting_in")
    if os.path.isdir(bundle):
        shutil.rmtree(bundle, ignore_errors=True)
    os.makedirs(bundle, exist_ok=True)

    _p(cb, 8, "Extracting meeting ZIP…")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(bundle)

    # 若仅一层子目录且其内才有文件，则下沉为该目录
    entries = [e for e in os.listdir(bundle) if not e.startswith(".")]
    if len(entries) == 1:
        only = os.path.join(bundle, entries[0])
        if os.path.isdir(only):
            inner = only
            for name in os.listdir(inner):
                shutil.move(os.path.join(inner, name), os.path.join(bundle, name))
            os.rmdir(inner)

    _p(cb, 25, "Transcribing meeting audio (iFlytek)…")
    transcriber = MeetingTranscriber(bundle)
    transcriber.process_meeting(understand_images=understand_images)

    mds = glob.glob(os.path.join(bundle, "meeting_summary_*.md"))
    if not mds:
        raise RuntimeError("No meeting_summary_*.md produced")
    mds.sort(key=os.path.getmtime)
    final_md = mds[-1]
    # 复制到 work_dir 根便于统一下载路径
    dest = os.path.join(work_dir, os.path.basename(final_md))
    shutil.copy2(final_md, dest)
    _p(cb, 100, "Meeting pipeline done")
    return dest
