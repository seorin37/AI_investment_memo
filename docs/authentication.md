# 소셜 OAuth·JWT 인증 운영 가이드

## 구현 구조

지원 공급자는 Google, Kakao, Naver뿐이며 이메일/비밀번호 인증은 제공하지 않는다.

1. 클라이언트가 `GET /api/v1/auth/{provider}/start`를 연다.
2. 백엔드는 state, 공급자 PKCE verifier/challenge, Google nonce를 생성한다.
3. 공급자 callback에서 state를 단일 사용으로 소비하고 Authorization Code를 교환한다.
4. `provider + provider_uid`로 사용자를 찾는다. 같은 이메일만으로 다른 공급자를 자동 연결하지 않는다.
5. 웹은 HttpOnly 쿠키를 받고, Android는 앱 딥링크로 3분짜리 단일 사용 교환 코드만 받은 뒤 앱 PKCE verifier로 세션을 교환한다.

Android 딥링크에는 Access/Refresh Token이 들어가지 않는다. 공급자 Access Token과 ID Token도 로그·URL·DB에 저장하지 않는다.

## 세션 정책

- Access Token: HS256 JWT, 15분, `iss`·`aud`·`exp`·`nbf`·`sid` 검증
- Refresh Token: 48바이트 난수, 14일, HMAC-SHA256 해시만 DB 저장
- 회전: 갱신할 때마다 새 세션 행과 Refresh Token 발급
- 재사용 탐지: 이미 회전·폐기된 Refresh Token이 다시 오면 같은 `family_id` 전체 폐기
- 즉시 로그아웃: 모든 인증 API가 JWT의 `sid`에 해당하는 활성 서버 세션을 확인하므로 로그아웃 후 기존 Access Token도 거부

웹 쿠키는 `HttpOnly`, 운영에서 `Secure`, `SameSite=Lax`를 사용한다. 쿠키 인증의 상태 변경 요청은 `memos_csrf` 쿠키와 `X-CSRF-Token` 헤더를 비교한다. 허용 CORS Origin과 OAuth 복귀 주소는 정확한 allowlist만 허용한다.

## 환경변수

루트 `.env.example`을 참고한다. 운영 필수 항목은 다음과 같다.

- `AUTH_JWT_SECRET`: 최소 32바이트 무작위 값
- `AUTH_PUBLIC_BASE_URL`: 외부에서 접근 가능한 HTTPS FastAPI 주소
- `AUTH_WEB_RETURN_URLS`: 쉼표 구분 웹 callback allowlist
- `AUTH_MOBILE_RETURN_URLS`: 기본값 `memos://auth/callback`
- `AUTH_CORS_ORIGINS`: 정확한 웹 Origin allowlist
- `AUTH_COOKIE_SECURE=true`: 운영에서 필수
- `AUTH_COOKIE_SAMESITE=lax`: 프론트와 API가 완전히 다른 사이트면 HTTPS에서만 `none` 검토
- `{GOOGLE|KAKAO|NAVER}_OAUTH_CLIENT_ID`, `_CLIENT_SECRET`

공급자 Console에는 다음 백엔드 callback 세 개를 등록한다.

```text
https://<API_HOST>/api/v1/auth/google/callback
https://<API_HOST>/api/v1/auth/kakao/callback
https://<API_HOST>/api/v1/auth/naver/callback
```

Google은 OIDC `openid email profile`, Kakao는 프로필·이메일 동의 항목, Naver는 회원 프로필 조회 권한을 설정한다. 이메일 동의가 없어도 계정은 생성할 수 있다. Google ID Token은 JWKS 서명, issuer, audience, expiry, nonce와 이메일 검증 상태를 확인한다.

## DB 마이그레이션

`0013_social_auth_sessions`는 다음 테이블만 추가한다.

- `oauth_transactions`: state·공급자 PKCE·복귀 주소의 단기 상태
- `auth_exchange_codes`: Android 단일 사용 교환 코드의 해시/PKCE challenge
- `auth_sessions`: Refresh Token 회전 이력과 폐기 상태

기존 `users`, `auth_identities`, `user_settings`와 데이터는 변경하지 않는다. 운영 적용 전 DB 백업, 현재 head `0012_financials_sector_columns` 확인, 격리 DB upgrade 테스트 후 별도로 적용한다.

## 개발 실행

백엔드:

```bash
PYTHONPATH=backend conda run -n ai_memo uvicorn app.main:app --host 0.0.0.0 --port 8000
```

웹:

```bash
cd frontend
EXPO_PUBLIC_USE_MOCK=false npx expo start --web
```

Android Studio 에뮬레이터용 Development Build:

```bash
cd frontend
npx expo run:android
```

`frontend/.env`에서 `EXPO_PUBLIC_ANDROID_API_BASE_URL=http://10.0.2.2:8000/api/v1`을 사용한다. `10.0.2.2`는 Android 에뮬레이터에서 호스트 PC를 가리킨다. Expo Go가 아니라 `scheme=memos`와 SecureStore가 포함된 Development Build로 확인한다.

수동 점검 순서:

1. Development Build에서 각 소셜 버튼을 누른다.
2. 시스템 브라우저가 열리고 공급자 동의 후 `memos://auth/callback?code=...`로 돌아오는지 확인한다.
3. 앱 URL과 로그에 JWT/Refresh Token이 없는지 확인한다.
4. 앱 재시작 후 SecureStore Refresh Token으로 세션이 복원되는지 확인한다.
5. 로그아웃 후 이전 Access/Refresh Token이 모두 거부되는지 확인한다.

운영 HTTPS에서는 검증된 App Link/Universal Link 도입을 권장한다. 현재 Development Build 시연은 custom scheme을 사용하며, 실제 Android App Link는 소유 도메인의 `assetlinks.json`과 Expo `intentFilters` 설정을 추가한 뒤 별도 검증해야 한다.

## 검증 상태

- 코드 구현: 완료
- Mock 기반 보안/계약 테스트: 완료
- 실제 Google/Kakao/Naver 로그인: Console 자격증명·redirect 등록 전 미검증
- Android Studio 에뮬레이터: 이 환경에서 실행하지 않아 미검증
- 운영 DB migration: 생성만 했으며 미적용
