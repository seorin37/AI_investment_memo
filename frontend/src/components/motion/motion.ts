/**
 * 모션 공통값 — 체험판(memo.html · x/app 스타일)의 CSS 변수를 그대로 옮김.
 *   --ease   cubic-bezier(.2,.8,.2,1)     부드럽게 멈춤
 *   --spring cubic-bezier(.34,1.45,.64,1) 살짝 넘쳤다 멈춤
 *   시트     cubic-bezier(.3,1.25,.5,1)
 * React Native 기본 Animated · Easing 만 씀 (애니메이션 추가 패키지 없음).
 * 기기의 '동작 줄이기'가 켜져 있으면 모든 시간이 0 → 바로 끝 상태 (체험판 --k 와 같은 역할).
 *
 * 모션 참고: Lucian UX/UI Prompt · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/
 */
import { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Platform } from 'react-native';

/** 웹(react-native-web)은 네이티브 드라이버가 없어서 JS로 돌림 */
export const ND = Platform.OS !== 'web';

export const EASE = Easing.bezier(0.2, 0.8, 0.2, 1);
export const SPRING = Easing.bezier(0.34, 1.45, 0.64, 1);
export const SHEET = Easing.bezier(0.3, 1.25, 0.5, 1);
export const STANDARD = Easing.bezier(0.2, 0, 0, 1);
export const BURST = Easing.bezier(0.2, 0.7, 0.3, 1);
export const SORT = Easing.bezier(0.3, 1.1, 0.4, 1);
export const MOVE = Easing.bezier(0.3, 1.15, 0.4, 1);
export const LINEAR = Easing.linear;

let reduce = false;
let deviceReduce = false;
let forcedOff = false;
let started = false;
const subs = new Set<(v: boolean) => void>();
const apply = () => { reduce = deviceReduce || forcedOff; subs.forEach((f) => f(reduce)); };
const set = (v: boolean) => { deviceReduce = v; apply(); };

/**
 * 앱 전체 모션 켜고 끄기 — 앱 시작 때(app/_layout.tsx) 한 번 부르면 됨.
 * false 면 모든 움직임이 바로 끝 상태로 (요청서의 "전환 효과 없음"으로 돌려야 할 때 · 테스트 캡처용).
 */
export function setMotionEnabled(on: boolean) { forcedOff = !on; apply(); }
function start() {
  if (started) return;
  started = true;
  AccessibilityInfo.isReduceMotionEnabled().then(set).catch(() => {});
  AccessibilityInfo.addEventListener('reduceMotionChanged', set);
}

/** 시간(ms) — 동작 줄이기면 0 */
export const ms = (d: number) => { start(); return reduce ? 0 : d; };

/** 반복 모션(숨쉬기 · 반짝임)을 멈출지 알 때 */
export function useReduceMotion(): boolean {
  const [r, setR] = useState(reduce);
  useEffect(() => { start(); subs.add(setR); setR(reduce); return () => { subs.delete(setR); }; }, []);
  return r;
}

export function useValue(v: number): Animated.Value {
  return useRef(new Animated.Value(v)).current;
}

export function tween(v: Animated.Value, toValue: number, duration: number, easing: (t: number) => number = EASE, native: boolean = ND, delay = 0) {
  return Animated.timing(v, { toValue, duration: ms(duration), easing, delay: ms(delay), useNativeDriver: native });
}

/**
 * 숫자 자체가 필요할 때(SVG 좌표 · 글자로 보이는 숫자) 목표값까지 따라가는 값.
 * 웹·앱 모두 같은 방식(JS)으로 움직임.
 */
export function useTweenNumber(target: number, duration: number, easing: (t: number) => number = EASE, from?: number, delay = 0): number {
  const v = useValue(from ?? target);
  const [n, setN] = useState(from ?? target);
  useEffect(() => {
    const id = v.addListener(({ value }) => setN(value));
    return () => v.removeListener(id);
  }, [v]);
  useEffect(() => {
    const a = tween(v, target, duration, easing, false, delay);
    a.start();
    return () => a.stop();
  }, [v, target, duration, easing, delay]);
  return n;
}

/** 0 → 1 로 한 번 (replay 값이 바뀌면 다시) — 차트 그리기 · 숫자 올라가기 */
export function useProgress(replay: unknown, duration: number, easing: (t: number) => number = EASE, delay = 0): number {
  const v = useValue(0);
  const [n, setN] = useState(0);
  useEffect(() => {
    const id = v.addListener(({ value }) => setN(value));
    return () => v.removeListener(id);
  }, [v]);
  useEffect(() => {
    v.setValue(0);
    const a = tween(v, 1, duration, easing, false, delay);
    a.start();
    return () => a.stop();
  }, [v, replay, duration, easing, delay]);
  return n;
}
