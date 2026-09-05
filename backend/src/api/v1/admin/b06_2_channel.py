# @ai-generated
"""
B06-2 渠道订单报表导出与佣金账单对账 API 路由
路由前缀：/api/v1/admin/b06-2
权限码：channel:export / channel:reconciliation

功能范围：
1. 订单报表导出（支持按时间、渠道编码、订单状态筛选）
2. 佣金账单导出（支持按时间、渠道编码、流水类型筛选）
3. 导出任务日志查询（后台审计）
4. 佣金账单对账汇总/明细查询
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.config.b06_2_constants import (
    EXPORT_FILE_DIR,
    EXPORT_FILE_PREFIX,
    EXPORT_FILE_TTL,
    EXPORT_MAX_DATE_RANGE_DAYS,
    EXPORT_MAX_FILE_SIZE,
    EXPORT_MAX_ROWS,
    LOCK_KEY_EXPORT,
    ORDER_EXPORT_COLUMNS,
    COMMISSION_BILL_COLUMNS,
    ORDER_STATUS_LABELS,
    FLOW_TYPE_LABELS,
    TRANSFER_STATUS_LABELS,
    PERM_CHANNEL_EXPORT,
    PERM_CHANNEL_RECONCILIATION,
    ExportTaskStatus,
    ExportTaskType,
)
from src.dao.b06_2_channel_dao import (
    ChannelCommissionBillQueryDAO,
    ChannelExportTaskLogDAO,
    ChannelOrderExportQueryDAO,
)
from src.db.init_db import DatabaseManager
from src.common.redis_client import RedisClient

logger = logging.getLogger("api.admin.b06_2_channel")

router = APIRouter(
    prefix="/api/v1/admin/b06-2",
    tags=["后台-渠道报表与对账(B06-2)"],
)


# ════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════


class OrderExportRequest(BaseModel):
    """订单报表导出请求参数"""
    channel_code: Optional[str] = Field(None, max_length=32, description="渠道标识，为空时导出全部渠道")
    order_status: Optional[int] = Field(None, ge=10, le=60, description="订单状态筛选")
    start_time: str = Field(..., description="起始时间(YYYY-MM-DD HH:mm:ss)")
    end_time: str = Field(..., description="截止时间(YYYY-MM-DD HH:mm:ss)")


class CommissionBillExportRequest(BaseModel):
    """佣金账单导出请求参数"""
    channel_code: Optional[str] = Field(None, max_length=32, description="渠道标识，为空时导出全部渠道")
    flow_type: Optional[str] = Field(None, max_length=32, description="流水类型：ORDER/SUPPLEMENT/DEDUCT")
    start_time: str = Field(..., description="起始时间(YYYY-MM-DD HH:mm:ss)")
    end_time: str = Field(..., description="截止时间(YYYY-MM-DD HH:mm:ss)")


class ExportTaskLogQueryParams(BaseModel):
    """导出任务日志查询参数"""
    task_type: Optional[str] = Field(None, description="任务类型：order_export/commission_bill")
    status: Optional[str] = Field(None, description="任务状态：PROCESSING/SUCCESS/FAILED")
    start_time: Optional[str] = Field(None, description="起始时间(YYYY-MM-DD HH:mm:ss)")
    end_time: Optional[str] = Field(None, description="截止时间(YYYY-MM-DD HH:mm:ss)")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class ReconciliationQueryParams(BaseModel):
    """对账查询参数"""
    channel_code: Optional[str] = Field(None, max_length=32, description="渠道标识，为空时查询全部")
    start_time: Optional[str] = Field(None, description="起始时间(YYYY-MM-DD HH:mm:ss)")
    end_time: Optional[str] = Field(None, description="截止时间(YYYY-MM-DD HH:mm:ss)")


# ════════════════════════════════════════════════════════════
# 依赖注入
# ════════════════════════════════════════════════════════════


async def get_export_admin(
    payload: dict = Depends(require_any_permission([PERM_CHANNEL_EXPORT])),
) -> dict:
    """获取后台管理员信息（订单报表导出权限）"""
    return {
        "user_id": int(payload["user_id"]),
        "user_name": payload.get("real_name", ""),
    }


async def get_reconciliation_admin(
    payload: dict = Depends(require_any_permission([PERM_CHANNEL_RECONCILIATION])),
) -> dict:
    """获取后台管理员信息（佣金账单对账权限）"""
    return {
        "user_id": int(payload["user_id"]),
        "user_name": payload.get("real_name", ""),
    }


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


# ════════════════════════════════════════════════════════════
# Excel 生成工具函数
# ════════════════════════════════════════════════════════════


def _create_excel_workbook(columns: List[tuple], rows: List[Dict[str, Any]]) -> Workbook:
    """创建 Excel 工作簿

    Args:
        columns: [(field_name, column_title), ...]
        rows: 数据行列表（dict，key 为 field_name）
    Returns:
        Workbook 对象
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # ── 样式定义 ──
    header_font = Font(name="微软雅黑", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_font = Font(name="微软雅黑", size=10)
    cell_alignment = Alignment(vertical="center", wrap_text=False)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # ── 写入表头 ──
    col_titles = [col[1] for col in columns]
    for col_idx, title in enumerate(col_titles, 1):
        cell = ws.cell(row=1, column=col_idx, value=title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # ── 写入数据 ──
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, (field_name, _) in enumerate(columns, 1):
            value = row_data.get(field_name, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font
            cell.alignment = cell_alignment
            cell.border = thin_border

    # ── 自动列宽 ──
    for col_idx, (_, title) in enumerate(columns, 1):
        # 计算该列最大宽度（取表头长度和内容最大长度）
        max_width = len(title) * 2  # 中文字符占2个单位
        for row_idx in range(2, len(rows) + 2):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if cell_value:
                # 粗略估算中文字符宽度
                char_len = sum(2 if ord(c) > 127 else 1 for c in str(cell_value))
                max_width = max(max_width, char_len)
        # 限制最大列宽
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_width + 4, 60)

    # 冻结首行
    ws.freeze_panes = "A2"

    return wb


def _format_order_row(order: Any) -> Dict[str, Any]:
    """格式化订单数据为导出行"""
    return {
        "internal_order_no": order.internal_order_no or "",
        "out_order_no": order.out_order_no or "",
        "goods_title": order.goods_title or "",
        "channel_code": order.channel_code or "",
        "pay_amount": str(round(float(order.pay_amount or 0), 2)),
        "total_commission": str(round(float(order.total_commission or 0), 2)),
        "user_commission": str(round(float(order.user_commission or 0), 2)),
        "platform_commission": str(round(float(order.platform_commission or 0), 2)),
        "order_status": ORDER_STATUS_LABELS.get(order.order_status, str(order.order_status or "")),
        "pay_time": order.pay_time.strftime("%Y-%m-%d %H:%M:%S") if order.pay_time else "",
        "settle_time": order.settle_time.strftime("%Y-%m-%d %H:%M:%S") if order.settle_time else "",
        "create_time": order.create_time.strftime("%Y-%m-%d %H:%M:%S") if order.create_time else "",
    }


def _format_commission_row(row: Any) -> Dict[str, Any]:
    """格式化佣金流水数据为导出行"""
    return {
        "internal_order_no": row.internal_order_no or "",
        "out_order_no": row.out_order_no or "",
        "user_id": str(row.user_id or ""),
        "channel_code": row.channel_code or "",
        "flow_type": FLOW_TYPE_LABELS.get(row.flow_type, row.flow_type or ""),
        "amount": str(round(float(row.amount or 0), 2)),
        "before_balance": str(round(float(row.before_balance or 0), 2)),
        "after_balance": str(round(float(row.after_balance or 0), 2)),
        "transfer_status": TRANSFER_STATUS_LABELS.get(row.transfer_status, row.transfer_status or ""),
        "create_time": row.create_time.strftime("%Y-%m-%d %H:%M:%S") if row.create_time else "",
    }


def _ensure_export_dir():
    """确保导出目录存在"""
    export_dir = os.path.join(os.getcwd(), EXPORT_FILE_DIR)
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def _validate_time_range(start_time: datetime, end_time: datetime):
    """校验时间范围不超过最大限制"""
    if start_time >= end_time:
        raise ValueError("起始时间必须早于截止时间")
    delta_days = (end_time - start_time).days
    if delta_days > EXPORT_MAX_DATE_RANGE_DAYS:
        raise ValueError(
            f"单次导出时间范围不能超过 {EXPORT_MAX_DATE_RANGE_DAYS} 天，"
            f"当前范围 {delta_days} 天"
        )


# ════════════════════════════════════════════════════════════
# 1. 订单报表导出
# ════════════════════════════════════════════════════════════


@router.post("/export/order")
async def export_order_report(
    request: Request,
    body: OrderExportRequest,
    admin_info: dict = Depends(get_export_admin),
    db: AsyncSession = Depends(get_db),
):
    """订单报表导出（异步导出，返回任务ID）

    参数校验规则：
    1. 时间范围不超过 31 天
    2. 导出行数不超过 10000 行
    3. 同一用户同时只能有一个导出任务
    """
    request_id = get_request_id(request)
    try:
        # 解析时间
        start_dt = datetime.strptime(body.start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(body.end_time, "%Y-%m-%d %H:%M:%S")
        _validate_time_range(start_dt, end_dt)

        # 检查是否有正在运行的任务
        task_log_dao = ChannelExportTaskLogDAO(db)
        running_task = await task_log_dao.check_running_task(admin_info["user_id"])
        if running_task:
            return error_response(
                msg=f"您有一个正在进行的导出任务(ID={running_task.id})，请等待完成后重试",
                request_id=request_id,
            )

        # 创建任务日志
        params = {
            "channel_code": body.channel_code or "",
            "order_status": body.order_status,
            "start_time": body.start_time,
            "end_time": body.end_time,
        }
        task_log = await task_log_dao.create_task_log(
            task_type=ExportTaskType.ORDER_EXPORT.value,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
            channel_code=body.channel_code or "",
            params=params,
        )

        # 查询订单数据
        query_dao = ChannelOrderExportQueryDAO(db)
        total_count = await query_dao.count_orders(
            channel_code=body.channel_code,
            order_status=body.order_status,
            start_time=start_dt,
            end_time=end_dt,
        )

        # 校验导出行数
        if total_count > EXPORT_MAX_ROWS:
            await task_log_dao.mark_failed(
                task_log.id,
                f"导出数据量({total_count}行)超过单次最大限制({EXPORT_MAX_ROWS}行)",
            )
            return error_response(
                msg=f"导出数据量({total_count}行)超过单次最大限制({EXPORT_MAX_ROWS}行)，请缩小时间范围或添加筛选条件",
                request_id=request_id,
            )

        if total_count == 0:
            await task_log_dao.mark_failed(task_log.id, "无符合条件的订单数据")
            return error_response(msg="无符合条件的订单数据", request_id=request_id)

        # 分页查询所有数据
        all_orders = []
        offset = 0
        while offset < total_count:
            page = await query_dao.query_orders(
                channel_code=body.channel_code,
                order_status=body.order_status,
                start_time=start_dt,
                end_time=end_dt,
                limit=EXPORT_MAX_ROWS,
                offset=offset,
            )
            if not page:
                break
            all_orders.extend(page)
            offset += len(page)

        # 生成 Excel
        rows = [_format_order_row(o) for o in all_orders]
        wb = _create_excel_workbook(ORDER_EXPORT_COLUMNS, rows)
        export_dir = _ensure_export_dir()
        file_name = f"{EXPORT_FILE_PREFIX}_order_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.xlsx"
        file_path = os.path.join(export_dir, file_name)

        wb.save(file_path)
        file_size = os.path.getsize(file_path)

        # 标记任务成功
        await task_log_dao.mark_success(
            log_id=task_log.id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            row_count=len(all_orders),
        )

        return success_response(
            data={
                "task_id": task_log.id,
                "file_name": file_name,
                "file_size": file_size,
                "row_count": len(all_orders),
                "status": ExportTaskStatus.SUCCESS.value,
            },
            msg="订单报表导出成功",
            request_id=request_id,
        )
    except ValueError as ve:
        return error_response(msg=str(ve), request_id=request_id)
    except Exception as exc:
        # 任务失败时更新日志
        try:
            task_log_dao = ChannelExportTaskLogDAO(db)
            if "task_log" in dir() and task_log:
                await task_log_dao.mark_failed(task_log.id, str(exc))
        except Exception:
            pass
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 佣金账单导出
# ════════════════════════════════════════════════════════════


@router.post("/export/commission-bill")
async def export_commission_bill(
    request: Request,
    body: CommissionBillExportRequest,
    admin_info: dict = Depends(get_export_admin),
    db: AsyncSession = Depends(get_db),
):
    """佣金账单导出（异步导出，返回任务ID）"""
    request_id = get_request_id(request)
    try:
        # 解析时间
        start_dt = datetime.strptime(body.start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(body.end_time, "%Y-%m-%d %H:%M:%S")
        _validate_time_range(start_dt, end_dt)

        # 检查是否有正在运行的任务
        task_log_dao = ChannelExportTaskLogDAO(db)
        running_task = await task_log_dao.check_running_task(admin_info["user_id"])
        if running_task:
            return error_response(
                msg=f"您有一个正在进行的导出任务(ID={running_task.id})，请等待完成后重试",
                request_id=request_id,
            )

        # 创建任务日志
        params = {
            "channel_code": body.channel_code or "",
            "flow_type": body.flow_type or "",
            "start_time": body.start_time,
            "end_time": body.end_time,
        }
        task_log = await task_log_dao.create_task_log(
            task_type=ExportTaskType.COMMISSION_BILL.value,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
            channel_code=body.channel_code or "",
            params=params,
        )

        # 查询佣金流水数据
        query_dao = ChannelCommissionBillQueryDAO(db)
        total_count = await query_dao.count_commission_flows(
            channel_code=body.channel_code,
            flow_type=body.flow_type,
            start_time=start_dt,
            end_time=end_dt,
        )

        # 校验导出行数
        if total_count > EXPORT_MAX_ROWS:
            await task_log_dao.mark_failed(
                task_log.id,
                f"导出数据量({total_count}行)超过单次最大限制({EXPORT_MAX_ROWS}行)",
            )
            return error_response(
                msg=f"导出数据量({total_count}行)超过单次最大限制({EXPORT_MAX_ROWS}行)，请缩小时间范围或添加筛选条件",
                request_id=request_id,
            )

        if total_count == 0:
            await task_log_dao.mark_failed(task_log.id, "无符合条件的佣金流水数据")
            return error_response(msg="无符合条件的佣金流水数据", request_id=request_id)

        # 分页查询所有数据
        all_flows = []
        offset = 0
        while offset < total_count:
            page = await query_dao.query_commission_flows(
                channel_code=body.channel_code,
                flow_type=body.flow_type,
                start_time=start_dt,
                end_time=end_dt,
                limit=EXPORT_MAX_ROWS,
                offset=offset,
            )
            if not page:
                break
            all_flows.extend(page)
            offset += len(page)

        # 生成 Excel
        rows = [_format_commission_row(r) for r in all_flows]
        wb = _create_excel_workbook(COMMISSION_BILL_COLUMNS, rows)
        export_dir = _ensure_export_dir()
        file_name = f"{EXPORT_FILE_PREFIX}_commission_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.xlsx"
        file_path = os.path.join(export_dir, file_name)

        wb.save(file_path)
        file_size = os.path.getsize(file_path)

        # 标记任务成功
        await task_log_dao.mark_success(
            log_id=task_log.id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            row_count=len(all_flows),
        )

        return success_response(
            data={
                "task_id": task_log.id,
                "file_name": file_name,
                "file_size": file_size,
                "row_count": len(all_flows),
                "status": ExportTaskStatus.SUCCESS.value,
            },
            msg="佣金账单导出成功",
            request_id=request_id,
        )
    except ValueError as ve:
        return error_response(msg=str(ve), request_id=request_id)
    except Exception as exc:
        try:
            task_log_dao = ChannelExportTaskLogDAO(db)
            if "task_log" in dir() and task_log:
                await task_log_dao.mark_failed(task_log.id, str(exc))
        except Exception:
            pass
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 导出任务日志查询
# ════════════════════════════════════════════════════════════


@router.get("/export/task-logs")
async def list_export_task_logs(
    request: Request,
    admin_info: dict = Depends(get_export_admin),
    db: AsyncSession = Depends(get_db),
    task_type: Optional[str] = Query(None, description="任务类型：order_export/commission_bill"),
    status: Optional[str] = Query(None, description="任务状态：PROCESSING/SUCCESS/FAILED"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """多条件查询导出任务日志"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None

        task_log_dao = ChannelExportTaskLogDAO(db)
        items, total = await task_log_dao.list_with_filters(
            task_type=task_type or None,
            status=status or None,
            operator_id=admin_info["user_id"] if task_type else None,
            start_time=start_dt,
            end_time=end_dt,
            page=page,
            page_size=page_size,
        )

        log_items = []
        for item in items:
            log_items.append({
                "id": item.id,
                "task_type": item.task_type,
                "channel_code": item.channel_code or "",
                "status": item.status,
                "file_name": item.file_name or "",
                "file_size": item.file_size or 0,
                "row_count": item.row_count or 0,
                "error_message": item.error_message or "",
                "operator_name": item.operator_name or "",
                "started_at": item.started_at.strftime("%Y-%m-%d %H:%M:%S") if item.started_at else None,
                "finished_at": item.finished_at.strftime("%Y-%m-%d %H:%M:%S") if item.finished_at else None,
                "params": json.loads(item.params) if item.params else {},
                "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            })

        return success_response(
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": log_items,
            },
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 佣金账单对账汇总
# ════════════════════════════════════════════════════════════


@router.get("/reconciliation/summary")
async def get_reconciliation_summary(
    request: Request,
    admin_info: dict = Depends(get_reconciliation_admin),
    db: AsyncSession = Depends(get_db),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识，为空时查询全部"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
):
    """佣金账单对账汇总"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None

        query_dao = ChannelCommissionBillQueryDAO(db)
        data = await query_dao.get_reconciliation_summary(
            channel_code=channel_code,
            start_time=start_dt,
            end_time=end_dt,
        )

        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 5. 佣金账单对账明细
# ════════════════════════════════════════════════════════════


@router.get("/reconciliation/detail")
async def get_reconciliation_detail(
    request: Request,
    admin_info: dict = Depends(get_reconciliation_admin),
    db: AsyncSession = Depends(get_db),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识，为空时查询全部"),
    flow_type: Optional[str] = Query(None, max_length=32, description="流水类型：ORDER/SUPPLEMENT/DEDUCT"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """佣金账单对账明细（分页查询）"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None

        query_dao = ChannelCommissionBillQueryDAO(db)
        total = await query_dao.count_commission_flows(
            channel_code=channel_code,
            flow_type=flow_type,
            start_time=start_dt,
            end_time=end_dt,
        )
        offset = (page - 1) * page_size
        items = await query_dao.query_commission_flows(
            channel_code=channel_code,
            flow_type=flow_type,
            start_time=start_dt,
            end_time=end_dt,
            limit=page_size,
            offset=offset,
        )

        flow_items = [_format_commission_row(r) for r in items]

        return success_response(
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": flow_items,
            },
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)