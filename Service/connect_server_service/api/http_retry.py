"""上位机 HTTP 请求的统一重试策略。"""
from typing import Optional

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_REQUEST_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = (500, 502, 503, 504)


def get_request_max_attempts(default: int = DEFAULT_REQUEST_ATTEMPTS) -> int:
    """从全局 INI 配置读取单次请求最大尝试次数。"""
    try:
        from public.config_class.global_setting import global_setting
        server = global_setting.get_setting("connect_server", {}).get("server", {})
        return max(1, int(server.get("request_retry_count", default)))
    except (AttributeError, TypeError, ValueError):
        return max(1, int(default))


def format_request_error(message: str, max_attempts: Optional[int] = None) -> str:
    """把最终网络异常转换为简短中文信息，弹窗不展示 requests 原始长文本。"""
    attempts = get_request_max_attempts() if max_attempts is None else max(1, int(max_attempts))
    detail = str(message or "")
    lowered = detail.lower()
    for status in RETRYABLE_STATUS_CODES:
        if str(status) in detail:
            return f"服务器连续 {attempts} 次请求失败（HTTP {status}），已停止自动请求，请稍后手动重连。"
    if "timeout" in lowered or "timed out" in lowered:
        return f"服务器连续 {attempts} 次请求超时，已停止自动请求，请稍后手动重连。"
    if "connection" in lowered or "连接" in detail:
        return f"连续 {attempts} 次无法连接服务器，已停止自动请求，请检查服务器状态。"
    return f"服务器请求连续失败 {attempts} 次，已停止自动请求，请稍后重试。"


def create_retry_session(max_attempts: Optional[int] = None) -> Session:
    """按 INI 配置创建 Session，只有最终失败才会进入界面错误回调。"""
    attempts = get_request_max_attempts() if max_attempts is None else max(1, int(max_attempts))
    retry = Retry(
        total=attempts - 1,
        connect=attempts - 1,
        read=attempts - 1,
        status=attempts - 1,
        other=attempts - 1,
        allowed_methods=None,
        status_forcelist=RETRYABLE_STATUS_CODES,
        backoff_factor=0.5,
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
