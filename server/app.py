import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.api.routes_health import router as health_router
from server.api.routes_parse import router as parse_router
from server.config import get_settings
from server.utils.exceptions import AppError
from server.utils.logger import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


settings = get_settings()
logger = logging.getLogger(__name__)
app = FastAPI(
    title="Personal Short Video Parser",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    message = first_error.get("msg", "请求参数校验失败。")
    safe_errors = []
    for error in exc.errors():
        copied = dict(error)
        if "ctx" in copied:
            copied["ctx"] = {key: str(value) for key, value in copied["ctx"].items()}
        safe_errors.append(copied)
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "details": {"errors": safe_errors},
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务内部异常，请查看后端日志排查。",
                "details": {},
            },
        },
    )


app.include_router(health_router)
app.include_router(parse_router)
