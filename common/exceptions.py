from fastapi import HTTPException, status
from typing import Optional, List, Any
from datetime import datetime, timezone

class APIException(HTTPException):
    def __init__(
            self, error: str,
            message: str,
            status_code: int, 
            error_code: Optional[str] = None,
            details: Optional[List[Any]] = None
    ):
        error_payload = {
            "error": error,
            "message": message,
            "error_code": error_code,
            "status": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if details: 
            error_payload["details"] = details

        super().__init__(
            status_code= status_code, 
            detail= error_payload
        )

class ValidationException(APIException):
    """400 Bad Request: Triggered when the user provides an invalid input."""
    def __init__(self, message: str, details: Optional[List[Any]] = None, error_code = "VALIDATION_ERROR"):
        super().__init__(
            error = "ValidationError", 
            message = message, 
            status_code = status.HTTP_400_BAD_REQUEST,
            error_code = error_code, 
            details = details
            )
        
class NotFoundException(APIException):
    """404 Not Found: Triggered when the requested data doesn't exist."""
    def __init__(self, message: str, error_code: str = "NOT_FOUND"):
        super().__init__(
            error = "NotFoundError", 
            message = message,
            status_code = status.HTTP_404_NOT_FOUND,
            error_code = error_code
        )

class ConflictException(APIException):
    """409 Conflict: Triggered for conflicting operations."""
    def __init__(self, message: str, details: Optional[List[Any]] = None, error_code: str = "CONFLICT"):
        super().__init__(
            error = "ConflictError",
            message = message, 
            status_code = status.HTTP_409_CONFLICT,
            error_code = error_code,
            details = details
        )

class InternalServerException(APIException):
    """500 Internal server Exception: Triggered when scrapers or database crashes."""
    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR"):
        super().__init__(
            error = "InternalServerError",
            message = message,
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code = error_code
        )