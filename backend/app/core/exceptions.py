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
