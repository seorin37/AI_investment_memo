import { useEffect } from 'react';
import { env } from '@/config/env';
import { canPlayFile } from '@/store/audioEngine';
import { useStudioPlayer } from '@/store/studioPlayer';
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

/** 막혀 있는 동안 완성된 오디오가 저절로 재생되지 않게 (store 는 웹과 같이 완성되면 재생을 켬). 앱 탭 레이아웃에서 한 번 */
export function useNoAutoplay() {
  useEffect(() => {
    if (!audioOff) return;
    return useStudioPlayer.subscribe((s) => {
      /* store 가 재생 타이머를 켠 다음에 끔 */
      if (s.playing) setTimeout(() => useStudioPlayer.getState().playing && useStudioPlayer.getState().toggle(), 0);
    });
  }, []);
}
