import { useEffect, useState } from 'react';
import { storage } from './storage';

/**
 * 서비스 설명(소개)을 본 적 있는지 (원본 웹 store.tsx 'memos.introSeen', 2026-11-21).
 * 기기 저장(lib/storage: 웹 localStorage · 앱 SecureStore). 웹은 처음 한 번만 /intro, 본 뒤엔 /login.
 */
export const INTRO_SEEN_KEY = 'memos.introSeen';

export const markIntroSeen = () => storage.set(INTRO_SEEN_KEY, '1');

/** 읽는 중이면 null. enabled=false 면 읽지 않고 null */
export function useIntroSeen(enabled: boolean): boolean | null {
  const [seen, setSeen] = useState<boolean | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    void storage.get(INTRO_SEEN_KEY).then((v) => alive && setSeen(v === '1'));
    return () => {
      alive = false;
    };
  }, [enabled]);
  return enabled ? seen : null;
}
