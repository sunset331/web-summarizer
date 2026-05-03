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

from elsepage import ElsepageSummarizer
from util.edge_driver_manager import ensure_edge_driver
from util.generate_summary import generate_summary
from util.generate_tags import generate_content_tags
from util.organize_by_tags import organize_by_tags
from util.process_url import process_url
from util.save_to_markdown import save_to_markdown
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
    status: str
    created_at: str
    updated_at: str
    message: str = ""
    output_path: Optional[str] = None


class UrlTaskRequest(BaseModel):
    url: HttpUrl
    api_key: str = ""
    model_name: str = ""


app = FastAPI(title="Web Summarizer Service", version="0.1.0")
app.mount("/ui", StaticFiles(directory=os.path.join(BASE_DIR, "ui"), html=True), name="ui")

_executor = ThreadPoolExecutor(max_workers=2)
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
    """Prefer typical private LAN ranges for display."""
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


def _pick_summarizer(url: str):
    if "xiaohongshu.com" in url or "xhslink.com" in url:
        return XiaohongshuSummarizer()
    if "zhihu.com" in url:
        return ZhihuSummarizer()
    if "mp.weixin.qq.com" in url:
        return WeixinSummarizer()
    return ElsepageSummarizer()


def _run_url_task(task_id: str, request: UrlTaskRequest):
    _update_task(task_id, status="running", message="Checking Edge driver version")
    ensure_edge_driver()

    _update_task(task_id, message="Fetching page and generating summary")
    summarizer = _pick_summarizer(str(request.url))
    out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "summary.md")

    summary = process_url(
        summarizer=summarizer,
        url=str(request.url),
        api_key=request.api_key,
        model_name=request.model_name,
        output_path=output_path,
    )
    if not summary:
        raise RuntimeError("Failed to produce summary")

    _update_task(
        task_id,
        status="done",
        message="Done",
        output_path=output_path,
    )


def _decode_uploaded_text(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", "gb2312"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unsupported file encoding; use UTF-8 or GBK text")


def _run_file_task(task_id: str, upload_path: str, original_name: str, api_key: str, model_name: str):
    _update_task(task_id, status="running", message="Reading uploaded file")
    with open(upload_path, "rb") as f:
        raw = f.read()

    text = _decode_uploaded_text(raw)
    if not text.strip():
        raise RuntimeError("Uploaded file is empty")

    _update_task(task_id, message="Generating summary and tags")
    summary = generate_summary(text, api_key=api_key, model_name=model_name)
    tags = generate_content_tags(text, api_key=api_key, model_name=model_name)

    out_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(original_name)[0] or "upload"
    output_path = os.path.join(out_dir, f"{base_name}_summary.md")

    source_url = f"file://{original_name}"
    save_to_markdown(source_url, summary, output_path, model_name, tags)
    organize_by_tags(output_path, tags)

    _update_task(
        task_id,
        status="done",
        message="Done",
        output_path=output_path,
    )


def _submit_task(kind: str) -> str:
    task_id = uuid.uuid4().hex[:12]
    with _task_lock:
        _tasks[task_id] = TaskRecord(
            task_id=task_id,
            kind=kind,
            status="pending",
            message="Queued",
            created_at=_now_str(),
            updated_at=_now_str(),
        )
    return task_id


def _safe_run(task_id: str, runner, *args):
    try:
        runner(task_id, *args)
    except Exception as exc:
        _update_task(task_id, status="failed", message=str(exc))


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
    """
    LAN base URLs for the same Wi-Fi / hotspot. All devices on that network can open these.
    """
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


@app.post("/api/tasks/url")
def create_url_task(request: UrlTaskRequest):
    task_id = _submit_task("url")
    _executor.submit(_safe_run, task_id, _run_url_task, request)
    return {"task_id": task_id}


@app.post("/api/tasks/file")
async def create_file_task(
    file: UploadFile = File(...),
    api_key: str = Form(default=""),
    model_name: str = Form(default=""),
):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in {".txt", ".md", ".markdown"}:
        raise HTTPException(status_code=400, detail="Only .txt / .md / .markdown are supported")

    task_id = _submit_task("file")
    upload_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    upload_path = os.path.join(upload_dir, file.filename or "upload.txt")

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _executor.submit(
        _safe_run, task_id, _run_file_task, upload_path, file.filename or "upload.txt", api_key, model_name
    )
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    data = asdict(task)
    if task.output_path:
        data["download_url"] = f"/api/tasks/{task_id}/download"
    return data


@app.get("/api/tasks/{task_id}/download")
def download_result(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done" or not task.output_path or not os.path.isfile(task.output_path):
        raise HTTPException(status_code=400, detail="Result not ready or missing")
    return FileResponse(task.output_path, filename=os.path.basename(task.output_path), media_type="text/markdown")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_service:app", host="0.0.0.0", port=8000, reload=False)
