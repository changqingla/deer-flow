"""处理文件上传的路由模块。"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.config.paths import VIRTUAL_PATH_PREFIX, get_paths
from src.sandbox.sandbox_provider import get_sandbox_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads/{thread_id}/uploads", tags=["uploads"])

# 需要转换为 Markdown 的文件扩展名
CONVERTIBLE_EXTENSIONS = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".doc",
    ".docx",
}


class UploadedFileInfo(BaseModel):
    """上传文件元数据。"""

    filename: str
    size: int
    path: str
    virtual_path: str
    artifact_url: str
    extension: str | None = None
    modified: float | None = None
    markdown_file: str | None = None
    markdown_path: str | None = None
    markdown_virtual_path: str | None = None
    markdown_artifact_url: str | None = None


class UploadResponse(BaseModel):
    """文件上传响应模型。"""

    success: bool
    files: list[UploadedFileInfo]
    message: str


class ListUploadsResponse(BaseModel):
    """上传文件列表响应模型。"""

    files: list[UploadedFileInfo]
    count: int


class DeleteUploadResponse(BaseModel):
    """删除上传文件操作响应模型。"""

    success: bool
    message: str


def get_uploads_dir(thread_id: str) -> Path:
    """获取线程 uploads 目录（不存在则创建）。

    参数：
        thread_id: 线程 ID。

    返回：
        uploads 目录路径。
    """
    try:
        base_dir = get_paths().sandbox_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _convert_file_to_markdown_sync(file_path: Path) -> Path | None:
    """同步将文件转换为 Markdown。

    参数：
        file_path: 待转换文件路径。

    返回：
        转换成功返回 Markdown 文件路径，否则返回 None。
    """
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(str(file_path))

        # 以同名 `.md` 文件落盘
        md_path = file_path.with_suffix(".md")
        md_path.write_text(result.text_content, encoding="utf-8")

        logger.info(f"Converted {file_path.name} to markdown: {md_path.name}")
        return md_path
    except Exception as e:
        logger.error(f"Failed to convert {file_path.name} to markdown: {e}")
        return None


async def convert_file_to_markdown(file_path: Path) -> Path | None:
    """在线程池中异步执行 Markdown 转换。"""
    return await asyncio.to_thread(_convert_file_to_markdown_sync, file_path)


def _normalize_filename(filename: str) -> str | None:
    """规范化并校验文件名。"""
    safe_filename = Path(filename).name
    if not safe_filename or safe_filename in {".", ".."}:
        return None
    if "/" in safe_filename or "\\" in safe_filename:
        return None
    return safe_filename


@router.post("", response_model=UploadResponse)
async def upload_files(
    thread_id: str,
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    """上传文件到线程目录，并按需转换为 Markdown。

    PDF/PPT/Excel/Word 文件会通过 markitdown 转换为 Markdown。
    原文件与转换文件都会保存到 `/mnt/user-data/uploads`。

    参数：
        thread_id: 目标线程 ID。
        files: 待上传文件列表。

    返回：
        包含成功状态与文件信息的上传响应。
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploads_dir = get_uploads_dir(thread_id)
    paths = get_paths()
    uploaded_files: list[dict[str, Any]] = []

    sandbox_provider = get_sandbox_provider()
    sandbox_id: str | None = None

    try:
        sandbox_id = sandbox_provider.acquire(thread_id)
        sandbox = sandbox_provider.get(sandbox_id)
        non_local_sandbox = sandbox if sandbox_id != "local" else None
        if sandbox_id != "local" and non_local_sandbox is None:
            raise HTTPException(status_code=500, detail=f"Sandbox not found: {sandbox_id}")

        for file in files:
            if not file.filename:
                continue

            try:
                safe_filename = _normalize_filename(file.filename)
                if safe_filename is None:
                    logger.warning(f"Skipping file with unsafe filename: {file.filename!r}")
                    continue

                content = await file.read()
                file_path = uploads_dir / safe_filename
                file_path.write_bytes(content)

                # 组装相对 backend 根目录的路径
                relative_path = str(paths.sandbox_uploads_dir(thread_id) / safe_filename)
                virtual_path = f"{VIRTUAL_PATH_PREFIX}/uploads/{safe_filename}"

                # 本地沙箱以线程宿主目录为唯一数据源；
                # 非本地沙箱需额外同步到虚拟路径，确保运行时可见。
                if sandbox_id != "local":
                    non_local_sandbox.update_file(virtual_path, content)

                file_info: dict[str, Any] = {
                    "filename": safe_filename,
                    "size": len(content),
                    "path": relative_path,  # 实际文件系统路径（相对 backend/）
                    "virtual_path": virtual_path,  # Agent 在沙箱中访问的路径
                    "artifact_url": f"/api/threads/{thread_id}/artifacts/mnt/user-data/uploads/{safe_filename}",  # HTTP 访问地址
                }

                logger.info(f"Saved file: {safe_filename} ({len(content)} bytes) to {relative_path}")

                # 检查文件是否需要转换为 Markdown
                file_ext = file_path.suffix.lower()
                if file_ext in CONVERTIBLE_EXTENSIONS:
                    md_path = await convert_file_to_markdown(file_path)
                    if md_path:
                        md_relative_path = str(paths.sandbox_uploads_dir(thread_id) / md_path.name)
                        md_virtual_path = f"{VIRTUAL_PATH_PREFIX}/uploads/{md_path.name}"

                        if sandbox_id != "local":
                            non_local_sandbox.update_file(md_virtual_path, md_path.read_bytes())

                        file_info["markdown_file"] = md_path.name
                        file_info["markdown_path"] = md_relative_path
                        file_info["markdown_virtual_path"] = md_virtual_path
                        file_info["markdown_artifact_url"] = f"/api/threads/{thread_id}/artifacts/mnt/user-data/uploads/{md_path.name}"

                uploaded_files.append(file_info)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to upload {file.filename}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")
    finally:
        if sandbox_id is not None:
            try:
                sandbox_provider.release(sandbox_id)
            except Exception:
                logger.exception("Failed to release sandbox %s after upload", sandbox_id)

    return UploadResponse(
        success=True,
        files=uploaded_files,
        message=f"Successfully uploaded {len(uploaded_files)} file(s)",
    )


@router.get("/list", response_model=ListUploadsResponse)
async def list_uploaded_files(thread_id: str) -> ListUploadsResponse:
    """列出线程 uploads 目录中的文件。

    参数：
        thread_id: 要查询的线程 ID。

    返回：
        包含文件元数据列表的响应对象。
    """
    uploads_dir = get_uploads_dir(thread_id)

    if not uploads_dir.exists():
        return ListUploadsResponse(files=[], count=0)

    files = []
    for file_path in sorted(uploads_dir.iterdir()):
        if file_path.is_file():
            stat = file_path.stat()
            relative_path = str(get_paths().sandbox_uploads_dir(thread_id) / file_path.name)
            files.append(
                {
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "path": relative_path,  # 实际文件系统路径
                    "virtual_path": f"{VIRTUAL_PATH_PREFIX}/uploads/{file_path.name}",  # Agent 在沙箱中访问的路径
                    "artifact_url": f"/api/threads/{thread_id}/artifacts/mnt/user-data/uploads/{file_path.name}",  # HTTP 访问地址
                    "extension": file_path.suffix,
                    "modified": stat.st_mtime,
                }
            )

    return ListUploadsResponse(files=files, count=len(files))


@router.delete("/{filename}", response_model=DeleteUploadResponse)
async def delete_uploaded_file(thread_id: str, filename: str) -> DeleteUploadResponse:
    """删除线程 uploads 目录中的指定文件。

    参数：
        thread_id: 线程 ID。
        filename: 待删除文件名。

    返回：
        删除结果消息。
    """
    uploads_dir = get_uploads_dir(thread_id)
    safe_filename = _normalize_filename(filename)
    if safe_filename is None or safe_filename != filename:
        raise HTTPException(status_code=400, detail=f"Invalid filename: {filename}")

    file_path = uploads_dir / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {safe_filename}")

    # 安全校验：确保路径位于 uploads 目录内
    try:
        file_path.resolve().relative_to(uploads_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    sandbox_provider = get_sandbox_provider()
    sandbox_id: str | None = None

    try:
        sandbox_id = sandbox_provider.acquire(thread_id)
        sandbox = sandbox_provider.get(sandbox_id)

        # 同步非本地沙箱中的文件状态
        if sandbox_id != "local":
            if sandbox is None:
                raise HTTPException(status_code=500, detail=f"Sandbox not found: {sandbox_id}")
            virtual_path = f"{VIRTUAL_PATH_PREFIX}/uploads/{safe_filename}"
            sandbox.delete_file(virtual_path)

        file_path.unlink()
        logger.info(f"Deleted file: {safe_filename}")
        return DeleteUploadResponse(success=True, message=f"Deleted {safe_filename}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete {safe_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete {safe_filename}: {str(e)}")
    finally:
        if sandbox_id is not None:
            try:
                sandbox_provider.release(sandbox_id)
            except Exception:
                logger.exception("Failed to release sandbox %s after delete", sandbox_id)
