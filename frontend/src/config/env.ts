/**
 * 런타임 환경 변수. Expo 는 빌드 시 EXPO_PUBLIC_* 값을 번들에 인라인합니다.
 * (process.env.EXPO_PUBLIC_X 형태로 '직접' 참조해야 인라인됩니다)
 */
import { Platform } from 'react-native';

const rawBase =
  Platform.OS === 'android'
    ? (process.env.EXPO_PUBLIC_ANDROID_API_BASE_URL ?? 'http://10.0.2.2:8000/api/v1')
    : (process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1');

const useMock = (process.env.EXPO_PUBLIC_USE_MOCK ?? 'true') === 'true';
const useRealStocks =
  !useMock || (process.env.EXPO_PUBLIC_USE_REAL_STOCKS ?? 'false') === 'true';
const useRealBoard =
  !useMock || (process.env.EXPO_PUBLIC_USE_REAL_BOARD ?? 'false') === 'true';
const useMockAuth = __DEV__ && useMock && !useRealStocks && !useRealBoard;

export const env = {
  apiBaseUrl: rawBase.replace(/\/+$/, ''),
  useMock,
  useRealStocks,
  useRealBoard,
  // Any real user-owned endpoint requires the normal OAuth/JWT session.
  useMockAuth,
  mockLatency: Number(process.env.EXPO_PUBLIC_MOCK_LATENCY ?? 250),
} as const;
