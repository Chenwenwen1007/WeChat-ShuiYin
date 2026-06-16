from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from server.schemas.request import ParseRequest
from server.schemas.response import ApiResponse, DirectLinkPayload, DownloadPayload, ParsePayload
from server.services.downloader_service import DownloadService
from server.services.parser_service import ParserService

router = APIRouter(prefix="/api", tags=["parser"])


def get_parser_service() -> ParserService:
    return ParserService()


def get_download_service() -> DownloadService:
    return DownloadService()


@router.post("/parse", response_model=ApiResponse[ParsePayload])
async def parse_video(
    body: ParseRequest,
    request: Request,
    parser_service: ParserService = Depends(get_parser_service),
) -> ApiResponse[ParsePayload]:
    result = await parser_service.parse(body.text, request, mode=body.mode)
    print(f"返回的ParsePayload: no_watermark_video_url={result.no_watermark_video_url[:50] if result.no_watermark_video_url else '空'}, no_watermark_download_url={result.no_watermark_download_url[:50] if result.no_watermark_download_url else '空'}, parse_source={result.parse_source}, no_watermark_verified={result.no_watermark_verified}")
    return ApiResponse(success=True, data=result)


@router.get("/download", response_class=StreamingResponse)
async def download_video(
    token: str,
    download_service: DownloadService = Depends(get_download_service),
) -> StreamingResponse:
    payload = download_service.decode_token(token)
    stream, headers, media_type = await download_service.build_stream(payload)
    return StreamingResponse(stream, headers=headers, media_type=media_type)


@router.get("/media", response_class=StreamingResponse)
async def proxy_media(
    token: str,
    download_service: DownloadService = Depends(get_download_service),
) -> StreamingResponse:
    payload = download_service.decode_token(token)
    stream, headers, media_type = await download_service.build_media_stream(payload)
    return StreamingResponse(stream, headers=headers, media_type=media_type)


@router.get("/platforms", response_model=ApiResponse[DownloadPayload])
async def supported_platforms() -> ApiResponse[DownloadPayload]:
    return ApiResponse(
        success=True,
        data=DownloadPayload(
            platforms=["douyin", "kuaishou", "xiaohongshu"],
            notes="解析依赖平台当前公开页面结构，平台改版后需要同步更新对应解析器。",
        ),
    )


@router.post("/direct-link", response_model=ApiResponse[DirectLinkPayload])
async def direct_link(
    body: ParseRequest,
    request: Request,
    download_service: DownloadService = Depends(get_download_service),
) -> ApiResponse[DirectLinkPayload]:
    source_url = body.text.strip()
    preview_url = download_service.build_media_url("external-link", source_url, "video", request)
    download_url = download_service.build_download_url_from_resource("external-link", source_url, request)
    return ApiResponse(
        success=True,
        data=DirectLinkPayload(
            title="外部直链",
            source_url=source_url,
            preview_url=preview_url,
            download_url=download_url,
        ),
    )
