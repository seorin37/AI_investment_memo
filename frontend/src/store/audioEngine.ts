import { Platform } from 'react-native';

/**
 * AI 오디오 실제 소리 (2026-11-24). 웹만: 브라우저 HTMLAudioElement 하나를 계속 쓴다.
 * 파일 주소는 같은 출처(/api/v1/studio/audio/{id}/file)라 로그인 쿠키가 그대로 간다.
 * 앱(네이티브)은 재생 모듈(expo-audio)이 아직 없어 canPlayFile=false → store가 예전처럼 시간만 흐르게 한다.
 */
export const canPlayFile = Platform.OS === 'web' && typeof window !== 'undefined' && typeof window.Audio === 'function';

export interface AudioHandlers {
  onTime(t: number): void;
  onEnd(): void;
  /** blocked: 브라우저가 사용자 동작 없는 자동 재생을 막음 (오류 안내는 하지 않는다) */
  onError(blocked: boolean): void;
}

let el: HTMLAudioElement | null = null;
let url = '';
let h: AudioHandlers | null = null;

function audio(): HTMLAudioElement {
  if (el) return el;
  const a = new window.Audio();
  a.preload = 'auto';
  a.addEventListener('timeupdate', () => h?.onTime(a.currentTime));
  a.addEventListener('ended', () => h?.onEnd());
  a.addEventListener('error', () => { if (url) h?.onError(false); });
  el = a;
  return a;
}

export const audioEngine = {
  /** url을 t초부터 rate 빠르기로. 같은 url이면 이어서 */
  play(src: string, t: number, rate: number, handlers: AudioHandlers) {
    if (!canPlayFile) return;
    const a = audio();
    h = handlers;
    if (url !== src) {
      url = src;
      a.src = src;
    }
    if (Math.abs(a.currentTime - t) > 0.5) a.currentTime = t;
    a.playbackRate = rate;
    a.play().catch((e: unknown) => {
      const blocked = e instanceof DOMException && e.name === 'NotAllowedError';
      const aborted = e instanceof DOMException && e.name === 'AbortError';   // 재생 중 멈춤·다른 파일로 바꿈
      if (!aborted) h?.onError(blocked);
    });
  },
  pause() {
    el?.pause();
  },
  seek(t: number) {
    if (el && url) el.currentTime = t;
  },
  rate(r: number) {
    if (el) el.playbackRate = r;
  },
  /** 로그아웃·미니 플레이어 닫기: 멈추고 파일을 놓는다 */
  stop() {
    if (!el) return;
    el.pause();
    url = '';
    h = null;
    el.removeAttribute('src');
    el.load();
  },
};
