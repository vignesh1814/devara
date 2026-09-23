"""Parser error types for the Devara compiler."""


class ParserError(Exception):
    """An error encountered during parsing."""

    def __init__(
        self,
        message: str,
        line: int,
        column: int,
        filename: str = "<stdin>",
    ) -> None:
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"{self.filename}:{self.line}:{self.column}: error: {self.message}"

    def __repr__(self) -> str:
        return (
            f"ParserError({self.message!r}, line={self.line}, col={self.column})"
        )
