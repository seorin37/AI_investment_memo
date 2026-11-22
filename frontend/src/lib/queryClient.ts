import { Platform } from 'react-native';
import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/api';

/**
 * 앱 전체에서 하나만 쓰는 react-query 캐시 (2026-11-22).
 * 컴포넌트 밖(store/auth.ts 의 로그아웃·계정 전환)에서도 비울 수 있게 모듈로 둔다.
 * 옵션은 예전 app/_layout.tsx 의 것과 같다.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, err) => !(err instanceof ApiError && [401, 403, 404].includes(err.status)) && count < 2,
      refetchOnWindowFocus: Platform.OS === 'web',
    },
  },
});
