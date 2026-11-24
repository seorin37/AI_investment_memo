import { useEffect, useState } from 'react';
import { env } from '@/config/env';
import { storage } from '@/lib/storage';
import { useAuth } from '@/store/auth';
import { quizDay } from './quizBank';

/** 남겨 둘 날짜 수 (저장할 때 이보다 오래된 기록은 지움) */
const KEEP_DAYS = 7;

type Answers = Record<string, number>;

/**
 * 오늘의 퀴즈 '하루 한 번' (2026-11-24). 서버 기록 API 가 없어서 기기에 저장 (lib/storage: 웹 localStorage · 앱 SecureStore).
 * 키: memos.quiz.{사용자 id} (mock 은 'mock') · 값: { "{퀴즈 날짜 번호}_{문제 slug}": 고른 번호 } JSON
 * 로그아웃해도 지우지 않음 → 같은 계정이 다시 들어와도 잠김. 날짜·문제가 바뀌면 키가 달라져 자동으로 안 푼 상태.
 * 제출은 문제가 확정되고(ready) · 사용자 id 가 있고 · 저장된 기록을 다 읽은 뒤에만.
 */
export function useQuizAnswer(slug: string, ready: boolean) {
  const uid = useAuth((s) => s.user?.id);
  const key = env.useMock ? 'memos.quiz.mock' : uid ? `memos.quiz.${uid}` : null;
  const [loaded, setLoaded] = useState<{ key: string; data: Answers } | null>(null);
  useEffect(() => {
    if (!key) return;
    let alive = true;
    void storage.get(key).then((v) => {
      if (!alive) return;
      let data: Answers = {};
      try {
        const parsed: unknown = v ? JSON.parse(v) : {};
        if (parsed && typeof parsed === 'object') data = parsed as Answers;
      } catch {
        /* 깨진 값은 빈 기록으로 */
      }
      setLoaded({ key, data });
    });
    return () => {
      alive = false;
    };
  }, [key]);
  const day = quizDay();
  const entry = `${day}_${slug}`;
  const mine = key && loaded?.key === key ? loaded.data : null;
  const done = mine && typeof mine[entry] === 'number' ? mine[entry] : null;
  const canSubmit = ready && !!mine && done === null;
  const submit = (i: number) => {
    if (!key || !mine || !ready || done !== null) return;
    const next: Answers = { [entry]: i };
    for (const [k, v] of Object.entries(mine)) if (Number(k.split('_')[0]) > day - KEEP_DAYS) next[k] = v;
    setLoaded({ key, data: next });
    void storage.set(key, JSON.stringify(next));
  };
  return { done, canSubmit, submit };
}
