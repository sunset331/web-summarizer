import ipaddress
import os
import shutil
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from starlette.middleware.cors import CORSMiddleware

from elsepage import ElsepageSummarizer
from util.edge_driver_manager import ensure_edge_driver
from util.process_url import process_url
from util.web_pipelines import run_audio_url_to_dir, run_meeting_zip_to_dir, run_video_file_to_dir
from util._save_raw_text import safe_filename
from weixin import WeixinSummarizer
from xiaohongshu import XiaohongshuSummarizer
from zhihu import ZhihuSummarizer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.join(BASE_DIR, "service_runtime")
UPLOAD_DIR = os.path.join(RUNTIME_DIR, "uploads")
OUTPUT_DIR = os.path.join(RUNTIME_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class TaskRecord:
    task_id: str
    kind: str
    module: str
    status: str
    created_at: str
    updated_at: str
    message: str = ""
    progress: int = 0
    output_path: Optional[str] = None


class UrlBody(BaseModel):
    url: HttpUrl


app = FastAPI(title="Web Summarizer", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/ui", StaticFiles(directory=os.path.join(BASE_DIR, "ui"), html=True), name="ui")

_executor = ThreadPoolExecutor(max_workers=1)
_tasks: Dict[str, TaskRecord] = {}
_task_lock = threading.Lock()


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _update_task(task_id: str, **kwargs):
    with _task_lock:
        task = _tasks[task_id]
        for key, value in kwargs.items():
            setattr(task, key, value)
        task.updated_at = _now_str()


def _is_usable_lan_ipv4(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        if addr.version != 4 or addr.is_loopback or addr.is_link_local or addr.is_multicast:
            return False
        return True
    except ValueError:
        return False


def _lan_sort_key(ip: str) -> tuple:
    try:
        a = ipaddress.ip_address(ip)
        if a in ipaddress.ip_network("10.0.0.0/8"):
            return (0, int(a))
        if a in ipaddress.ip_network("192.168.0.0/16"):
            return (1, int(a))
        if a in ipaddress.ip_network("172.16.0.0/12"):
            return (2, int(a))
        return (3, int(a))
    except ValueError:
        return (9, 0)


def _collect_lan_ipv4() -> List[str]:
    found: set[str] = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if _is_usable_lan_ipv4(ip):
                found.add(ip)
        finally:
            s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if _is_usable_lan_ipv4(ip):
                found.add(ip)
    except OSError:
        pass
    return sorted(found, key=_lan_sort_key)


def _advertised_port() -> str:
    return os.environ.get("WEB_SUMMARIZER_PORT", os.environ.get("PORT", "8000"))


def _pick_summarizer(url: str):
    if "xiaohongshu.com" in url or "xhslink.com" in url:
        return XiaohongshuSummarizer()
    if "zhihu.com" in url:
        return ZhihuSummarizer()
    if "mp.weixin.qq.com" in url:
        return WeixinSummarizer()
    return ElsepageSummarizer()


def _submit_task(kind: str, module: str) -> str:
    task_id = uuid.uuid4().hex[:12]
    with _task_lock:
        _tasks[task_id] = TaskRecord(
            task_id=task_id,
            kind=kind,
            module=module,
            status="pending",
            created_at=_now_str(),
            updated_at=_now_str(),
            message="Queued",
            progress=0,
        )
    return task_id


def _safe_run(task_id: str, runner, *args):
    try:
        runner(task_id, *args)
    except Exception as exc:
        _update_task(task_id, status="failed", message=str(exc), progress=0)


def _task_progress_cb(task_id: str):
    def cb(pct: int, msg: str):
        _update_task(task_id, progress=pct, message=msg)

    return cb


def _run_web_url_task(task_id: str, body: UrlBody):
    _update_task(task_id, status="running", message="Checking Edge driver", progress=3)
    ensure_edge_driver()
    _update_task(task_id, message="Fetching page", progress=15)
    summarizer = _pick_summarizer(str(body.url))
    out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "summary.md")

    summary, md_path = process_url(
        summarizer=summarizer,
        url=str(body.url),
        api_key="",
        model_name="",
        output_path=output_path,
    )
    if not summary or not md_path:
        raise RuntimeError("Failed to produce summary")

    _update_task(
        task_id,
        status="done",
        message="Done — download the Markdown summary",
        progress=100,
        output_path=md_path,
    )


def _run_audio_url_task(task_id: str, body: UrlBody):
    out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(out_dir, exist_ok=True)
    _update_task(task_id, status="running", message="Starting audio pipeline", progress=2)

    md_path = run_audio_url_to_dir(str(body.url), out_dir, cb=_task_progress_cb(task_id))

    _update_task(
        task_id,
        status="done",
        message="Done — download the Markdown summary",
        progress=100,
        output_path=md_path,
    )


def _run_video_upload_task(task_id: str, upload_path: str, sample_rate: int):
    out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(out_dir, exist_ok=True)
    _update_task(task_id, status="running", message="Starting video analysis", progress=2)

    md_path = run_video_file_to_dir(
        upload_path, out_dir, sample_rate=sample_rate, cb=_task_progress_cb(task_id)
    )

    try:
        os.remove(upload_path)
    except OSError:
        pass

    _update_task(
        task_id,
        status="done",
        message="Done — download the Markdown report",
        progress=100,
        output_path=md_path,
    )


def _run_meeting_zip_task(task_id: str, zip_path: str, understand_images: bool):
    out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(out_dir, exist_ok=True)
    _update_task(task_id, status="running", message="Starting meeting pipeline", progress=2)

    md_path = run_meeting_zip_to_dir(
        zip_path, out_dir, understand_images=understand_images, cb=_task_progress_cb(task_id)
    )

    try:
        os.remove(zip_path)
    except OSError:
        pass

    _update_task(
        task_id,
        status="done",
        message="Done — download the Markdown meeting notes",
        progress=100,
        output_path=md_path,
    )


@app.on_event("startup")
def _log_listen():
    p = _advertised_port()
    ips = _collect_lan_ipv4()
    print("[INFO] LAN IPv4:", ", ".join(ips) or "(none)")
    for ip in ips:
        print(f"[INFO]   Open: http://{ip}:{p}/")


@app.get("/", response_class=HTMLResponse)
def index_page():
    index_path = os.path.join(BASE_DIR, "ui", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/health")
def health_check():
    return {"status": "ok", "time": _now_str()}


@app.get("/api/service-urls")
def service_urls(request: Request):
    port = request.url.port
    if port is None:
        port = 443 if request.url.scheme == "https" else 80
    scheme = request.url.scheme or "http"
    port_part = ""
    if (scheme == "http" and port != 80) or (scheme == "https" and port != 443):
        port_part = f":{port}"
    ipv4s = _collect_lan_ipv4()
    lan_base_urls = [f"{scheme}://{ip}{port_part}/" for ip in ipv4s]
    primary = lan_base_urls[0] if lan_base_urls else str(request.base_url).rstrip("/") + "/"
    return {
        "lan_ipv4": ipv4s,
        "lan_base_urls": lan_base_urls,
        "primary_share_url": primary,
        "port": port,
        "scheme": scheme,
        "request_base_url": str(request.base_url).rstrip("/") + "/",
    }


@app.post("/api/tasks/web/url")
def create_web_url_task(body: UrlBody):
    task_id = _submit_task("web_url", "web")
    _executor.submit(_safe_run, task_id, _run_web_url_task, body)
    return {"task_id": task_id}


@app.post("/api/tasks/audio/url")
def create_audio_url_task(body: UrlBody):
    task_id = _submit_task("audio_url", "audio")
    _executor.submit(_safe_run, task_id, _run_audio_url_task, body)
    return {"task_id": task_id}


@app.post("/api/tasks/video/upload")
async def create_video_upload_task(
    file: UploadFile = File(...),
    sample_rate: int = Form(default=3),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}:
        raise HTTPException(status_code=400, detail="Video: use mp4 / mkv / mov / webm / avi / m4v")

    task_id = _submit_task("video_upload", "video")
    upload_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    raw_name = safe_filename(file.filename or "video.mp4")
    upload_path = os.path.join(upload_dir, raw_name)
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        sr = int(sample_rate)
    except (TypeError, ValueError):
        sr = 3

    _executor.submit(_safe_run, task_id, _run_video_upload_task, upload_path, sr)
    return {"task_id": task_id}


@app.post("/api/tasks/meeting/upload")
async def create_meeting_upload_task(
    file: UploadFile = File(...),
    understand_images: str = Form(default="true"),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".zip":
        raise HTTPException(status_code=400, detail="Meeting: upload a .zip of audio + screenshots folder")

    task_id = _submit_task("meeting_zip", "meeting")
    upload_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    zip_path = os.path.join(upload_dir, "meeting_bundle.zip")
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    ui = understand_images.strip().lower() in ("1", "true", "yes", "on")
    _executor.submit(_safe_run, task_id, _run_meeting_zip_task, zip_path, ui)
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    data = asdict(task)
    if task.output_path and task.status == "done":
        data["download_url"] = f"/api/tasks/{task_id}/download"
    return data


@app.get("/api/tasks/{task_id}/download")
def download_result(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done" or not task.output_path or not os.path.isfile(task.output_path):
        raise HTTPException(status_code=400, detail="Result not ready or missing")
    name = os.path.basename(task.output_path)
    return FileResponse(task.output_path, filename=name, media_type="text/markdown")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_service:app", host="0.0.0.0", port=8000, reload=False)
