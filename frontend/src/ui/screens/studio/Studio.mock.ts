import type { MadeItem, StudioFeatureItem } from './Studio.types';

/**
 * 스튜디오 mock (원본 app/studio.html · web studio.tsx). 사용량·크레딧·갱신일·플랜은 My.mock 에서 읽는다.
 * 실제 결과는 서버가 만들어 돌려줄 값 — 지금은 화면 확인용.
 */
export const mockStudioFeatures: StudioFeatureItem[] = [
  { key: 'audio', title: 'AI 오디오', desc: '바쁠 땐 내 종목 소식을 라디오로' },
  { key: 'report', title: 'AI 주간보고서', desc: '공시 읽기 힘드셨죠? 한 주를 한 장으로' },
  { key: 'lab', title: 'AI 투자 실험실', desc: '금리·환율이 바뀌면 내 종목은?' },
  { key: 'quiz', title: '오늘의 퀴즈', desc: '어제 증시에서 일어난 일 1문제 · 무료' },
];

export const mockMade: MadeItem[] = [
  { id: 'm1', kind: 'audio', title: '11.06 내 종목 라디오', sub: '어제 소식과, 그때 내가 남긴 메모', meta: '오디오 · 3종목 · 전날 · 6:42', left: '27일 뒤 삭제', dur: '6:42', foot: '종목 3개 · 전날 기준' },
  { id: 'm2', kind: 'report', title: '10월 다섯째 주 돌아보기', sub: '주간보고서 · 종목 3개', meta: '주간보고서 · 3종목', left: '23일 뒤 삭제' },
  { id: 'm3', kind: 'lab', title: '삼성전자 · 환율 하락 실험', sub: '투자 실험실 · 삼성전자', meta: '투자 실험실 · 삼성전자', left: '25일 뒤 삭제' },
];

/** 웹 스튜디오 머리 (내 종목 N · AI 연결 메모 N) */
export const mockStudioCounts = { stock_count: 3, ai_memo_count: 5 };
