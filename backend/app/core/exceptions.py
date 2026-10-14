"""Domain and business logic exceptions for IncidentHub."""


class DomainException(Exception):
    """Base class for all domain-specific exceptions."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class EntityNotFoundError(DomainException):
    """Raised when an entity is not found."""

    pass


class DuplicateEntityError(DomainException):
    """Raised when an entity violates unique constraints or already exists."""

    pass


class DomainValidationError(DomainException):
    """Raised when a business rule or invariant is violated."""

    pass


class AuthenticationError(DomainException):
    """Raised when authentication fails, credentials are invalid, or a token is rejected."""

    def __init__(
        self,
        message: str = "Could not validate credentials",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.headers = headers or {"WWW-Authenticate": "Bearer"}


class PermissionDeniedError(DomainException):
    """Raised when an authenticated user lacks required permissions for an operation."""

    def __init__(
        self,
        message: str = "Insufficient permissions for this operation",
    ) -> None:
        super().__init__(message)


class TenantContextMissingError(DomainException):
    """Raised when an operation requires an organization/tenant context that was not provided."""

    def __init__(
        self,
        message: str = "Tenant context is required for this operation",
    ) -> None:
        super().__init__(message)
