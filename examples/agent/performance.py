import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from app.api.v1.agent.performance_agents import (
    performance_result_stream,
    start_performance_analysis,
)
from app.schemas.performance import PerformanceAnalysisResult, PerformanceReport
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/performance", tags=["performance"])

# 存储上传的性能报告
UPLOAD_DIR = "uploads/performance_reports"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 存储分析结果
RESULTS_DIR = "results/performance_analysis"
os.makedirs(RESULTS_DIR, exist_ok=True)

# 内存中暂存的文件信息
uploaded_files = {}


@router.post("/upload")
async def upload_performance_report(file: UploadFile = File(...)):
    """
    上传性能报告文件
    """
    try:
        # 确保文件是合法的性能报告文件
        if not is_valid_performance_file(file):
            raise HTTPException(status_code=400, detail="无效的性能报告文件格式")

        # 生成唯一ID并保存文件
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_extension}")

        # 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 记录文件信息
        uploaded_files[file_id] = {
            "id": file_id,
            "filename": file.filename,
            "path": file_path,
            "upload_time": datetime.now().isoformat(),
            "size": len(content),
            "status": "uploaded",
        }

        return JSONResponse(
            {
                "success": True,
                "file_id": file_id,
                "message": "文件上传成功",
                "fileUrl": f"/api/v1/agent/performance/file/{file_id}",
            }
        )

    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"文件上传失败: {str(e)}"}, status_code=500
        )


@router.get("/file/{file_id}")
async def get_performance_file(file_id: str):
    """
    获取已上传的性能报告文件
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件不存在")

    file_info = uploaded_files[file_id]

    async def file_reader():
        with open(file_info["path"], "rb") as f:
            yield f.read()

    return StreamingResponse(
        file_reader(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={file_info['filename']}"
        },
    )


@router.get("/analyze")
async def analyze_performance(file_id: str = Query(..., description="上传的文件ID")):
    """
    分析性能报告并返回结果流
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件不存在")

    file_info = uploaded_files[file_id]

    # 启动分析任务
    analysis_task = asyncio.create_task(start_performance_analysis(file_info["path"]))

    # 创建SSE响应
    return StreamingResponse(
        performance_result_stream(), media_type="text/event-stream"
    )


@router.get("/results/{file_id}")
async def get_analysis_results(file_id: str):
    """
    获取已完成的性能分析结果
    """
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件不存在")

    result_path = os.path.join(RESULTS_DIR, f"{file_id}.json")

    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="分析结果不存在")

    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    return result


# 辅助函数


def is_valid_performance_file(file: UploadFile) -> bool:
    """
    验证上传的文件是否为有效的性能报告文件
    """
    valid_extensions = [".json", ".html", ".har", ".csv", ".xml"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in valid_extensions:
        return False

    # 进一步验证文件内容可在此处添加

    return True
