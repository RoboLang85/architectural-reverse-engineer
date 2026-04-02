"""Error hierarchy for the Architectural Reverse Engineer."""


class AnalyzerError(Exception):
    """Base error for all analyzer operations."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InputError(AnalyzerError):
    """Raised when input validation fails (invalid paths, URLs, etc.)."""


class GitError(AnalyzerError):
    """Raised when a git operation (clone, fetch) fails."""


class UnsupportedFileError(AnalyzerError):
    """Raised when an unsupported file type is provided."""

    def __init__(self, message: str, supported_types: list[str] | None = None, details: dict | None = None) -> None:
        super().__init__(message, details)
        self.supported_types = supported_types or ["pdf", "docx", "png", "jpg", "svg"]


class FileReadError(AnalyzerError):
    """Raised when a file cannot be read (corrupted, permissions, etc.)."""


class ExtractionError(AnalyzerError):
    """Raised when content extraction from a document fails."""


class AIServiceError(AnalyzerError):
    """Raised when the AI service (OpenAI API) encounters an error."""


class RenderError(AnalyzerError):
    """Raised when diagram rendering (Graphviz, PlantUML) fails."""


class SchemaValidationError(AnalyzerError):
    """Raised when JSON Schema validation fails."""

    def __init__(self, message: str, validation_errors: list[str] | None = None, details: dict | None = None) -> None:
        super().__init__(message, details)
        self.validation_errors = validation_errors or []
