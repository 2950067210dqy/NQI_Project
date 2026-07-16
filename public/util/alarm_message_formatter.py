"""报警/预警消息显示格式化工具。"""
import re

OPERATOR_TEXT = {
    "gt": "大于",
    "ge": "大于等于",
    "lt": "小于",
    "le": "小于等于",
    "eq": "等于",
    "ne": "不等于",
    "enabled": "启用即告警",
}

SEVERITY_TEXT = {
    "critical": "严重",
    "warning": "预警",
    "info": "提示",
}

STATUS_TEXT = {
    "open": "未处理",
    "acknowledged": "已确认",
    "closed": "已关闭",
    "unread": "未读",
    "read": "已读",
}

SOURCE_TEXT = {
    "auto": "自动检测",
    "manual": "人工录入",
}

METRIC_TEXT = {
    "file_size_kb": "文件大小(KB)",
    "sheet_count": "Sheet数量",
    "numeric_value_count": "数值数量",
    "max_numeric_value": "Excel 全表数值单元格最大值",
    "min_numeric_value": "Excel 全表数值单元格最小值",
    "avg_numeric_value": "Excel 全表数值单元格平均值",
    "chart_point_count": "图表测试点数量",
    "chart_value_count": "图表数据数量",
    "error_value_count": "误差数据数量",
    "processing_failed": "数据解析失败",
    "upload_error": "数据上传错误",
    "original_size_kb": "原始文件大小(KB)",
    "compression_ratio": "几何量压缩率",
    "mean_brightness": "图片平均亮度",
    "brightness_std": "图片亮度波动",
    "contrast_score": "图片对比度",
    "sharpness_score": "图片清晰度",
    "image_width": "图片宽度",
    "image_height": "图片高度",
    "power_w": "功率(W)",
    "power": "功率",
    "voltage": "电压",
    "current": "电流",
    "phase_angle": "相角",
}

STAT_TEXT = {
    "max": "最大值",
    "min": "最小值",
    "avg": "平均值",
    "count": "数量",
}


def display_status(value: str) -> str:
    return STATUS_TEXT.get(str(value or ""), str(value or ""))


def display_severity(value: str) -> str:
    return SEVERITY_TEXT.get(str(value or ""), str(value or ""))


def display_source(value: str) -> str:
    return SOURCE_TEXT.get(str(value or ""), str(value or ""))


def display_operator(value: str) -> str:
    return OPERATOR_TEXT.get(str(value or ""), str(value or ""))


def _display_scope_name(value: str) -> str:
    """把 sheet/相位的内部编码转成界面显示名称。"""
    text = str(value or "")
    return text.upper() if len(text) == 1 and text.isalpha() else text


def display_metric_key(metric_key: str) -> str:
    """把服务端 metric_key 转成给操作人员看的中文名称。"""
    key = str(metric_key or "")
    if not key:
        return ""
    if key in METRIC_TEXT:
        return METRIC_TEXT[key]

    # 误差和统计后缀必须先解析，再递归解析前面的 sheet/相位/指标部分。
    error_match = re.match(r"^(.+)_error_(percent|ppm)_abs_(max|avg|min)$", key)
    if error_match:
        base_key, unit_name, stat_name = error_match.groups()
        unit_text = "百分比" if unit_name == "percent" else "ppm"
        return f"{display_metric_key(base_key)}{unit_text}误差绝对值{STAT_TEXT.get(stat_name, stat_name)}"

    stat_match = re.match(r"^(.+)_(max|min|avg|count)$", key)
    if stat_match:
        base_key, stat_name = stat_match.groups()
        return f"{display_metric_key(base_key)}{STAT_TEXT.get(stat_name, stat_name)}"

    sheet_phase_match = re.match(r"^sheet_([^_]+)_phase_([^_]+)_(.+)$", key)
    if sheet_phase_match:
        sheet_name, phase_name, rest_key = sheet_phase_match.groups()
        return f"Sheet {_display_scope_name(sheet_name)} {_display_scope_name(phase_name)}相 {display_metric_key(rest_key)}"

    sheet_match = re.match(r"^sheet_([^_]+)_(.+)$", key)
    if sheet_match:
        sheet_name, rest_key = sheet_match.groups()
        return f"Sheet {_display_scope_name(sheet_name)} {display_metric_key(rest_key)}"

    phase_match = re.match(r"^phase_([^_]+)_(.+)$", key)
    if phase_match:
        phase_name, rest_key = phase_match.groups()
        return f"{_display_scope_name(phase_name)}相 {display_metric_key(rest_key)}"

    return key


_RULE_EXPR_RE = re.compile(
    r"(?P<metric>[A-Za-z][A-Za-z0-9_]*?)=(?P<value>-?\d+(?:\.\d+)?)\s+"
    r"(?P<op>gt|ge|lt|le|eq|ne|enabled)\s+"
    r"(?P<threshold>-?\d+(?:\.\d+)?)"
)

_METRIC_TOKEN_RE = re.compile(r"\b(?:sheet_[A-Za-z0-9_]+|phase_[A-Za-z0-9_]+|max_numeric_value|min_numeric_value|avg_numeric_value|numeric_value_count|power(?:_[A-Za-z0-9_]+)?|power_w(?:_[A-Za-z0-9_]+)?|voltage(?:_[A-Za-z0-9_]+)?|current(?:_[A-Za-z0-9_]+)?|phase_angle(?:_[A-Za-z0-9_]+)?|file_size_kb|original_size_kb|compression_ratio|mean_brightness|brightness_std|contrast_score|sharpness_score|image_width|image_height|processing_failed|upload_error)\b")


def format_alarm_message(message: str) -> str:
    """把报警消息中的规则码、指标码和操作符转换成中文。"""
    text = str(message or "")
    if not text:
        return ""

    def replace_expr(match):
        metric = display_metric_key(match.group("metric"))
        value = match.group("value")
        operator = match.group("op")
        threshold = match.group("threshold")
        if operator == "enabled":
            return f"{metric}已触发"
        # 用自然语言描述阈值关系，避免把 lt/gt 等内部比较码暴露给操作人员。
        relation = {
            "gt": "高于阈值", "ge": "大于等于阈值", "lt": "低于阈值",
            "le": "小于等于阈值", "eq": "等于阈值", "ne": "不等于阈值",
        }.get(operator, display_operator(operator))
        return f"{metric}当前值为 {value}，{relation} {threshold}"

    text = _RULE_EXPR_RE.sub(replace_expr, text)

    def replace_metric(match):
        return display_metric_key(match.group(0))

    text = _METRIC_TOKEN_RE.sub(replace_metric, text)
    for op, op_text in OPERATOR_TEXT.items():
        text = re.sub(rf"\b{op}\b", op_text, text)
    return text
