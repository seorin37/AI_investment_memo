/**
 * 런타임 환경 변수. Expo 는 빌드 시 EXPO_PUBLIC_* 값을 번들에 인라인합니다.
 * (process.env.EXPO_PUBLIC_X 형태로 '직접' 참조해야 인라인됩니다)
 */
const rawBase = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export const env = {
  apiBaseUrl: rawBase.replace(/\/+$/, ''),
  useMock: (process.env.EXPO_PUBLIC_USE_MOCK ?? 'true') === 'true',
  mockLatency: Number(process.env.EXPO_PUBLIC_MOCK_LATENCY ?? 250),
} as const;
