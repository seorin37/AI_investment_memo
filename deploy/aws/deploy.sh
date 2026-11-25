#!/usr/bin/env bash
# EC2 재배포: 최신 dev 받기 → 웹 빌드 → API·Caddy 재시작 → 수집 이미지·실시간 뉴스 재시작
# 사용: ~/AI_investment_memo/deploy/aws/deploy.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

echo "== 1/5 최신 코드 받기"
git pull --ff-only

echo "== 2/5 웹 빌드 (frontend/dist)"
docker run --rm -v "$REPO/frontend":/app -w /app node:22 \
  sh -c "npm ci && npm run export:web:same-origin"

echo "== 3/5 API·Caddy 재시작"
cd "$REPO/deploy/aws"
docker compose -f compose.prod.yml up -d --build

echo "== 4/5 수집 이미지 갱신 + 실시간 뉴스 재시작"
docker build -f "$REPO/deploy/aws/Dockerfile.worker" -t memos-worker "$REPO"
docker compose -f compose.worker.yml up -d --force-recreate news

echo "== 5/5 확인"
docker compose -f compose.prod.yml ps
docker ps --filter name=memos-news --format "{{.Names}}  {{.Status}}"
sleep 5
curl -fsS https://memos-sig.duckdns.org/health && echo "  <- health OK"
