import { env } from '@/config/env';
import { useHomeNews } from '@/hooks/queries';
import { mockHomeNow } from './Home.mock';
import type { HomeData } from './Home.types';

/**
 * 홈 뉴스 위젯 데이터 (2026-11-21): HOME_NEWS 대신 GET /news/home 을 화면 props 모양으로.
 * - 웹(템플릿·맞춤 홈)과 앱 홈이 같이 쓴다
 * - news_day 는 가장 새 기사의 한국 날짜, news_day_total 은 그날 종목 연결 기사 수
 * - now 는 실제 시각 ('N분 전' 계산). mock 모드만 예시 데이터와 맞춘 mockHomeNow
 * - 받는 중이거나 실패하면 빈 목록 (위젯은 머리 기사 없이 그려진다)
 */
export function useHomeNewsProps(): Pick<HomeData, 'news' | 'news_day_total' | 'news_day' | 'now'> {
  const { data } = useHomeNews();
  return {
    news: data?.items ?? [],
    news_day_total: data?.day_total ?? 0,
    news_day: data?.day ?? undefined,
    now: env.useMock ? mockHomeNow : new Date().toISOString(),
  };
}
