import uvicorn

from server.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "server.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
