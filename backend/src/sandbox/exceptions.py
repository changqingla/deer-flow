"""沙箱相关异常，包含结构化错误信息。"""


class SandboxError(Exception):
    """所有沙箱相关错误的基类异常。"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class SandboxNotFoundError(SandboxError):
    """当沙箱不存在或不可用时抛出。"""

    def __init__(self, message: str = "Sandbox not found", sandbox_id: str | None = None):
        details = {"sandbox_id": sandbox_id} if sandbox_id else None
        super().__init__(message, details)
        self.sandbox_id = sandbox_id


class SandboxRuntimeError(SandboxError):
    """当沙箱运行时不可用或配置错误时抛出。"""

    pass


class SandboxCommandError(SandboxError):
    """当沙箱内命令执行失败时抛出。"""

    def __init__(self, message: str, command: str | None = None, exit_code: int | None = None):
        details = {}
        if command:
            details["command"] = command[:100] + "..." if len(command) > 100 else command
        if exit_code is not None:
            details["exit_code"] = exit_code
        super().__init__(message, details)
        self.command = command
        self.exit_code = exit_code


class SandboxFileError(SandboxError):
    """当沙箱内文件操作失败时抛出。"""

    def __init__(self, message: str, path: str | None = None, operation: str | None = None):
        details = {}
        if path:
            details["path"] = path
        if operation:
            details["operation"] = operation
        super().__init__(message, details)
        self.path = path
        self.operation = operation


class SandboxPermissionError(SandboxFileError):
    """当文件操作过程中发生权限错误时抛出。"""

    pass


class SandboxFileNotFoundError(SandboxFileError):
    """当文件或目录不存在时抛出。"""

    pass
