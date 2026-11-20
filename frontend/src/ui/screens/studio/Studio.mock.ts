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

/** 오디오 만들기 시트 종목 (원본 STK: 이름 · 새 소식 수 · 보유/관심) */
/** news: 기간별 새 소식 수 [전날, 최근 3일, 최근 7일] (앱 시트는 전날 값만 보여 줌) */
export interface AudioStock { stock_code: string; name: string; news: [number, number, number]; hold: '보유' | '관심' }
export const mockAudioStocks: AudioStock[] = [
  { stock_code: '000660', name: 'SK하이닉스', news: [3, 4, 6], hold: '보유' },
  { stock_code: '005930', name: '삼성전자', news: [2, 3, 5], hold: '관심' },
  { stock_code: '035420', name: '네이버', news: [0, 0, 1], hold: '관심' },
];
export const mockAudioPeriods = ['전날', '최근 3일', '최근 7일'] as const;
/** 직전 거래일 (웹 시트 '증시 요약' 아래 줄) */
export const mockLastClose = '11.18(화)';

/** 만들기 단계 · 결과 이름 (원본 GK.audio) */
export const mockAudioGen = {
  steps: ['업데이트 모으기', '두 진행자 대본 쓰기', '목소리 입히기'],
  result_title: '오늘의 내 종목 라디오',
};

/**
 * 오디오 한 편 (원본 09 플레이어 CH · SC). 길이·시각은 초. 실제 소리는 없음 (mock 타이머).
 * 금지 문구 규칙: 매수·매도 권유 · 호재/악재 · 가격 전망 · 장중 · 기대감류 없음, 시세는 'MM.DD 종가 기준'
 */
export const mockAudioEpisode = {
  hosts: ['진행자 A · 메인', '진행자 B · 해설'],
  dur: 402,
  chapters: [[0, '어제 증시 요약'], [28, 'SK하이닉스'], [70, '삼성전자'], [108, '네이버 · 새 소식 없음'], [122, '마무리']] as [number, string][],
  script: [
    [0, 'A', '오늘은 고른 종목 3곳의 소식을 살펴볼게요. 먼저 어제 증시부터요.'],
    [12, 'B', '11.06 종가 기준으로 코스피는 1.2% 올랐고, 원/달러 환율은 조금 내렸어요.'],
    [28, 'A', 'SK하이닉스로 가 볼까요? 전에 HBM 수요 메모를 남기셨는데, 관련 소식이 있다고요?'],
    [44, 'B', '네. 10월 30일 신규 시설투자 공시가 나왔고, 추적 중인 HBM 항목과 연결됐어요.'],
    [58, 'A', '그럼 메모와는 어떤 관계로 보면 될까요?'],
    [63, 'B', '공시에는 투자 대상과 기간이 나와 있어요. 메모의 "HBM 생산 능력" 항목과 같은 주제라 연결했어요.'],
    [70, 'A', '다음은 삼성전자예요.'],
    [76, 'B', '삼성전자는 11월 5일 자기주식 취득 결정 공시가 있었어요. 취득 기간과 수량은 원문에 있어요.'],
    [108, 'A', '네이버는 이번 기간에 새 소식이 없었어요.'],
    [122, 'B', '오늘은 여기까지예요. 판단은 메모와 원문을 보고 직접 해 주세요.'],
  ] as [number, 'A' | 'B', string][],
  sources: [
    { kind: '공시', text: 'SK하이닉스 · 신규 시설투자 · DART · 10.30', memo: '메모 “HBM 수요 계속 확인”와 연결' },
    { kind: '공시', text: '삼성전자 · 자기주식 취득 결정 · DART · 11.05', memo: '' },
    { kind: '뉴스', text: 'HBM4 공급 확대 보도 · 한국경제 · 11.06', memo: '' },
  ],
  market_source: '11.06 코스피·코스닥·원/달러 종가',
  memo_link: {
    head: 'SK하이닉스 · AI 연결',
    title: 'HBM 수요 계속 확인',
    body: '10월 30일 신규 시설투자 공시가 이 메모의 추적 항목 "HBM 생산 능력"과 연결됐어요. 오디오에서는 공시 내용과 메모의 관계를 설명했어요.',
    seek: 51,
    count: '공시 1건',
  },
};

/** 웹 스튜디오 머리 (내 종목 N · AI 연결 메모 N) */
export const mockStudioCounts = { stock_count: 3, ai_memo_count: 5 };
