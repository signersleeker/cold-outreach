from typing import Any

from fastapi.responses import JSONResponse


def data_body(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": _jsonable(data)})


def list_body(data: Any, meta: Any | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": _jsonable(data), "meta": _jsonable(meta if meta is not None else {})},
    )


def error_body(status_code: int, *messages: str) -> JSONResponse:
    if not messages:
        messages = ("an unexpected error occurred",)
    return JSONResponse(
        status_code=status_code,
        content={"errors": [{"message": m} for m in messages]},
    )


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value
