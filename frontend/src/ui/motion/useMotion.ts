import { useSyncExternalStore } from 'react';
import { AccessibilityInfo, Platform } from 'react-native';

/**
 * 동작 줄이기 (원본 motion.css: prefers-reduced-motion 이면 --k = .01)
 * 기기 설정을 한 번 읽고, 바뀌면 따라감. 화면은 시간에 k 를 곱해서 씀.
 */
let reduced = false;
const subs = new Set<() => void>();
let started = false;

function start() {
  if (started) return;
  started = true;
  void AccessibilityInfo.isReduceMotionEnabled().then((v) => {
    reduced = v;
    subs.forEach((f) => f());
  });
  AccessibilityInfo.addEventListener('reduceMotionChanged', (v) => {
    reduced = v;
    subs.forEach((f) => f());
  });
}

function subscribe(f: () => void) {
  start();
  subs.add(f);
  return () => {
    subs.delete(f);
  };
}

/** 속도 배수: 보통 1, 동작 줄이기면 0.01 */
export function useMotionK(): number {
  return useSyncExternalStore(subscribe, () => (reduced ? 0.01 : 1), () => 1);
}

/** Animated 의 useNativeDriver — 웹은 지원하지 않음 */
export const NATIVE = Platform.OS !== 'web';
