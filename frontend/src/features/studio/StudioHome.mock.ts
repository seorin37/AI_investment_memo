/** 스튜디오 예시 — 체험판 (웹과 같은 이름·설명·순서) */
import type { StudioHomeProps } from '@/features/studio/StudioHome.types';

const noop = () => {};

export const mockStudioHomeProps: StudioHomeProps = {
  usage_percent: 62,
  features: [
    { key: 'audio', title: 'AI 오디오', desc: '바쁠 땐 내 종목 소식을 라디오로' },
    { key: 'report', title: 'AI 주간보고서', desc: '공시 읽기 힘드셨죠? 한 주를 한 장으로' },
    { key: 'lab', title: 'AI 투자 실험실', desc: '금리·환율이 바뀌면 내 종목은?' },
    { key: 'quiz', title: '오늘의 퀴즈', desc: '어제 증시에서 일어난 일 1문제 · 무료' },
  ],
  featured_audio: { id: 'au1', title: '11.06 내 종목 라디오', sub: '어제 소식과, 그때 내가 남긴 메모', duration: '6:42', meta: '종목 3개 · 전날 기준', expire_label: '27일 뒤 삭제', progress: 0.22 },
  made: [
    { id: 'rp1', kind: 'report', title: '10월 다섯째 주 돌아보기', sub: '주간보고서 · 종목 3개', expire_label: '23일 뒤 삭제' },
    { id: 'lb1', kind: 'lab', title: '삼성전자 · 환율 하락 실험', sub: '투자 실험실 · 삼성전자', expire_label: '25일 뒤 삭제' },
  ],
  onOpenUsage: noop,
  onOpenFeature: noop,
  onPlayAudio: noop,
  onOpenMade: noop,
};
