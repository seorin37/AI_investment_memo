/**
 * 숫자가 올라가며 보임 (Lucian #098 kpi-count-up) — 홈 요약 숫자 · 종가 · 지표.
 * 처음 보일 때 0(또는 from)에서 값까지 .9s ease, 값이 바뀌면 이전 값에서 새 값까지.
 * format 으로 쉼표 · 소수 · 단위를 붙임 (숫자 계산은 서버/코드 값 그대로, 화면 표시만 움직임).
 */
import { Text, type StyleProp, type TextStyle } from 'react-native';
import { EASE, useTweenNumber } from '@/components/motion/motion';

export const fmtInt = (n: number) => Math.round(n).toLocaleString('ko-KR');

export function CountUp({ value, format = fmtInt, from = 0, duration = 900, delay = 0, style, numberOfLines }: {
  value: number; format?: (n: number) => string; from?: number; duration?: number; delay?: number; style?: StyleProp<TextStyle>; numberOfLines?: number;
}) {
  const n = useTweenNumber(value, duration, EASE, from, delay);
  /** 다 올라가면 정확한 값으로 (반올림 오차 없게) */
  const shown = Math.abs(n - value) < 1e-6 ? value : n;
  return <Text style={style} numberOfLines={numberOfLines} accessibilityLabel={format(value)}>{format(shown)}</Text>;
}

/** '131.4조' · '58,980원' · '3.06배' 처럼 글로 온 값에서 숫자 부분만 올라가게 (앞뒤 글자 · 소수 자릿수 · 쉼표는 그대로) */
export function CountUpText({ text, duration = 900, delay = 0, style, numberOfLines }: {
  text: string; duration?: number; delay?: number; style?: StyleProp<TextStyle>; numberOfLines?: number;
}) {
  const m = /^([^\d-]*)(-?[\d,]*\.?\d+)(.*)$/.exec(text);
  if (!m) return <Text style={style} numberOfLines={numberOfLines}>{text}</Text>;
  const [, pre, raw, post] = m;
  const dec = (raw.split('.')[1] ?? '').length;
  const comma = raw.includes(',');
  const format = (n: number) => pre + (comma ? n.toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec }) : n.toFixed(dec)) + post;
  return <CountUp value={parseFloat(raw.replace(/,/g, ''))} format={format} duration={duration} delay={delay} style={style} numberOfLines={numberOfLines} />;
}
