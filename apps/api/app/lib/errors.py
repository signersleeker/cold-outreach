from dataclasses import dataclass


@dataclass
class AppError(Exception):
    status_code: int
    messages: tuple[str, ...]

    def __init__(self, status_code: int, *messages: str) -> None:
        self.status_code = status_code
        self.messages = messages if messages else ("an unexpected error occurred",)
        super().__init__(self.messages[0])
