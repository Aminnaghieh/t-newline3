"""Custom error types and error handling utilities."""

from __future__ import annotations


class LiaraAgentError(Exception):
    """Base error for all liara-agent errors."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.message = message
        self.hint = hint
        super().__init__(message)


class LiaraApiError(LiaraAgentError):
    """Error from Liara REST API."""

    def __init__(
        self,
        status_code: int,
        message: str,
        endpoint: str = "",
        hint: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(
            f"[HTTP {status_code}] {endpoint}: {message}",
            hint=hint or self._default_hint(status_code),
        )

    @staticmethod
    def _default_hint(status_code: int) -> str:
        hints = {
            400: "درخواست نامعتبر — پارامترهای ورودی را بررسی کنید",
            401: "احراز هویت ناموفق — توکن API را با 'liara-agent config' تنظیم کنید",
            403: "دسترسی غیرمجاز — مجوزهای توکن را بررسی کنید",
            404: "ریسورس یافت نشد — نام پروژه/اپلیکیشن را بررسی کنید",
            409: "تداخل — عملیات دیگری در حال اجرا است، لطفاً صبر کنید",
            429: "محدودیت نرخ درخواست — چند ثانیه صبر کنید و دوباره تلاش کنید",
            500: "خطای سرور لیارا — لطفاً بعداً تلاش کنید یا با پشتیبانی تماس بگیرید",
            502: "سرویس لیارا موقتاً در دسترس نیست",
            503: "سرویس لیارا در حال نگهداری است",
        }
        return hints.get(status_code, "خطای ناشناخته — لطفاً دوباره تلاش کنید")


class RateLimitError(LiaraApiError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 60, endpoint: str = "") -> None:
        self.retry_after = retry_after
        super().__init__(
            status_code=429,
            message=f"Rate limit exceeded. Retry after {retry_after}s",
            endpoint=endpoint,
            hint=f"محدودیت نرخ — {retry_after} ثانیه صبر کنید",
        )


class AuthenticationError(LiaraAgentError):
    """Authentication/token error."""

    def __init__(self, message: str = "توکن API تنظیم نشده یا نامعتبر است") -> None:
        super().__init__(
            message,
            hint="با دستور 'liara-agent config' توکن را تنظیم کنید",
        )


class ProjectNotFoundError(LiaraAgentError):
    """Project does not exist."""

    def __init__(self, project_name: str) -> None:
        super().__init__(
            f"پروژه '{project_name}' یافت نشد",
            hint="لیست پروژه‌ها را با 'liara-agent service list' بررسی کنید",
        )


class DeploymentError(LiaraAgentError):
    """Deployment failed."""

    def __init__(self, message: str, project_name: str = "") -> None:
        super().__init__(
            f"خطا در دیپلوی{f' {project_name}' if project_name else ''}: {message}",
            hint="لاگ‌های دیپلوی را با 'liara-agent logs' بررسی کنید",
        )


class ConfigurationError(LiaraAgentError):
    """Configuration missing or invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"خطای پیکربندی: {message}",
            hint="فایل .env را بررسی کنید یا 'liara-agent config' را اجرا کنید",
        )


class ApprovalDeniedError(LiaraAgentError):
    """User denied approval for an operation."""

    def __init__(self, operation: str) -> None:
        super().__init__(
            f"عملیات '{operation}' توسط کاربر رد شد",
            hint="عملیات لغو شد. هیچ تغییری اعمال نشد.",
        )


class AnalysisError(LiaraAgentError):
    """Error during project analysis."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"خطا در تحلیل پروژه: {message}",
            hint="مطمئن شوید در پوشه‌ ریشه پروژه هستید",
        )
