"""웹 정적 빌드(expo export --platform web)를 API와 같은 주소에서 서빙한다.

같은 주소(origin)에서 웹을 열면 memos_csrf 쿠키를 document.cookie로 읽을 수 있어
쿠키 세션의 CSRF 검사(double-submit)가 통과하고, 서드파티 쿠키 차단도 받지 않는다.

- /api/* 는 건드리지 않는다 (없는 API는 JSON 404).
- 빌드에 있는 파일은 그 파일을, 그 밖의 경로(/auth/callback 등 SPA 경로)는 index.html 을 준다.
- WEB_DIST_DIR (기본: <repo>/frontend/dist) 에 index.html 이 없으면 아무것도 등록하지 않는다.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

log = logging.getLogger(__name__)

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
# Expo 웹 빌드의 해시가 붙은 번들 폴더. 이름이 바뀌면 다시 받으므로 오래 캐시해도 된다.
IMMUTABLE_PREFIXES = ("_expo/static/",)
RESERVED_PREFIXES = ("api/", "docs", "redoc", "openapi.json", "health")


def web_dist_dir(environ=None) -> Path:
    env = os.environ if environ is None else environ
    configured = env.get("WEB_DIST_DIR", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_DIST


def mount_web(app: FastAPI, dist: Path | None = None) -> bool:
    """앱의 다른 라우트를 모두 등록한 뒤 마지막에 부른다. 등록했으면 True."""
    root = (dist or web_dist_dir()).resolve()
    index = root / "index.html"
    if not index.is_file():
        log.info("web build not found, SPA serving disabled: %s", root)
        return False

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def serve_web(full_path: str):
        if full_path == "api" or full_path.startswith(RESERVED_PREFIXES):
            raise HTTPException(404, detail="Not Found")
        if full_path:
            candidate = (root / full_path).resolve()
            if candidate.is_file() and root in candidate.parents:
                headers = (
                    {"Cache-Control": "public, max-age=31536000, immutable"}
                    if full_path.startswith(IMMUTABLE_PREFIXES)
                    else None
                )
                return FileResponse(candidate, headers=headers)
        # SPA 경로: 새 배포가 바로 보이도록 index.html 은 캐시하지 않는다.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    log.info("serving web build from %s", root)
    return True
