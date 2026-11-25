import { env } from '@/config/env';
import { canPlayFile } from '@/store/audioEngine';
import { useUI } from '@/store/ui';

/** 앱 실제 모드인데 재생 모듈이 없음 → 재생 버튼을 막음 (mock 모드는 예전처럼 시간만 흐름) */
export const audioOff = !env.useMock && !canPlayFile;
/** 막힌 버튼 바탕 (스튜디오 만들기 버튼의 못 누르는 색과 같음) */
export const AUDIO_OFF_BG = '#C9CDD4';

/** 재생을 시작하기 전에: 막혀 있으면 안내하고 true */
export function blockPlay(): boolean {
  if (audioOff) useUI.getState().showToast('앱에서 듣기는 곧 열려요');
  return audioOff;
}
