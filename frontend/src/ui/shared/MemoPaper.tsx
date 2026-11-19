import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Path, Polygon } from 'react-native-svg';

/**
 * 메모지 바탕 (RN 에는 clip-path 가 없어 종이 모양을 경로로 그림)
 * - 라운드 위 왼쪽·위 오른쪽·아래 왼쪽 r, 아래 오른쪽은 cut 만큼 비스듬히 잘림
 * app: 원본 memo.html .grid .face (r16 · cut 24) + .corner (24 · 위 왼쪽 라운드 7 · 접힌 부분 색)
 * web: 원본 board.tsx .paper-cut (r16 · cut 30) + .m-fold (30×30 'M0 9C0 3 3 0 9 0H30L0 30V9Z')
 */
export function PaperFace({ width, height, bg, accent, variant, radius = 16, cut, style }: { width: number; height: number; bg: string; accent: string; variant: 'app' | 'web'; radius?: number; cut?: number; style?: StyleProp<ViewStyle> }) {
  const c = cut ?? (variant === 'app' ? 24 : 30);
  const r = radius;
  const w = width;
  const h = height;
  const d = `M${r} 0H${w - r}A${r} ${r} 0 0 1 ${w} ${r}V${h - c}L${w - c} ${h}H${r}A${r} ${r} 0 0 1 0 ${h - r}V${r}A${r} ${r} 0 0 1 ${r} 0Z`;
  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, style]}>
      <Svg width={w} height={h}>
        <Path d={d} fill={bg} />
        {variant === 'app' ? (
          /* 접힌 부분: (w-c, h-c) 위 왼쪽 라운드 7 · 오른쪽 위 · 왼쪽 아래 삼각형 */
          <Path d={`M${w - c} ${h - c + 7}A7 7 0 0 1 ${w - c + 7} ${h - c}H${w}L${w - c} ${h}Z`} fill={accent} />
        ) : (
          <Path d="M0 9C0 3 3 0 9 0H30L0 30V9Z" fill={accent} transform={`translate(${w - 30} ${h - 30})`} />
        )}
      </Svg>
    </View>
  );
}

/* 원본 .tape clip-path (57×19, 톱니 4% · 17% 간격) */
const APP_TAPE_PTS = [
  [0, 0], [57, 0], [54.72, 3.23], [57, 6.27], [54.72, 9.5], [57, 12.73], [54.72, 15.77], [57, 19],
  [0, 19], [2.28, 15.77], [0, 12.73], [2.28, 9.5], [0, 6.27], [2.28, 3.23],
].map((p) => p.join(',')).join(' ');

/** 앱 고정 테이프 (원본 .tape: 57×19 · 위 -8 · 가운데 · -3° · 불투명도 .82 · 접힌 부분 색) */
export function AppTape({ color }: { color: string }) {
  return (
    <View pointerEvents="none" style={st.appTape}>
      <Svg width={57} height={19}>
        <Polygon points={APP_TAPE_PTS} fill={color} opacity={0.82} />
      </Svg>
    </View>
  );
}

/* 원본 board.tsx 테이프 경로 */
export const TAPE_ON = 'M0 3.76855L71.9013 0.000365913L68.5998 3.87847L72.2834 7.29036L68.9818 11.1685L72.6707 14.6802L69.3639 18.4585L73.0527 21.9702L1.15139 25.7384L4.45295 21.8603L0.769339 18.4484L4.0709 14.5703L0.382052 11.0586L3.68885 7.28031L0 3.76855Z';
export const TAPE_LIFT = 'M6 12L76.9062 -0.50267L74.1018 3.74889L78.1738 6.68643L75.3695 10.938L79.4588 13.974L76.6371 18.1271L80.7264 21.1631L9.82026 33.6658L12.6246 29.4142L8.55263 26.4767L11.357 22.2251L7.26763 19.1891L10.0893 15.036L6 12Z';
export const TAPE_DASH =
  'M69.499 4.72852L71 6.27051V6.27148L70.4619 6.79395L70.96 7.30664L70.4551 7.8418L70.999 8.35645L69.5 9.94238L68.9551 9.42773L67.9551 10.4844L67.4678 11L67.9551 11.5156L68.9551 12.5723L69.5 12.0576V12.0566L70.999 13.6426H71L70.4551 14.1582L70.96 14.6924L70.4619 15.2061L71 15.7285L69.499 17.2705L68.9619 16.749L67.9619 17.7773L67.4609 18.293L67.9551 18.8154L68.9551 19.8721L69.5 19.3574V19.3564L70.999 20.9424H71L70.6748 21.25H69.9424V22H66.8574V21.25H62.7432V22H59.6572V21.25H55.543V22H52.457V21.25H48.3428V22H45.2568V21.25H41.1426V22H38.0576V21.25H33.9424V22H30.8574V21.25H26.7432V22H23.6572V21.25H19.543V22H16.457V21.25H12.3428V22H9.25684V21.25H5.14258V22H2.05762V21.25H1.3252L1 20.9424L2.49902 19.3564L2.5 19.3574L3.04492 19.8721L4.04492 18.8154L4.53906 18.293L4.03809 17.7773L3.03809 16.749L2.5 17.2705L0.999023 15.7285L1.53809 15.2061L1.03906 14.6924L1.54492 14.1582L1 13.6426L2.49902 12.0566L2.5 12.0576L3.04492 12.5723L4.04492 11.5156L4.53223 11L4.04492 10.4844L3.04492 9.42773L2.49902 9.94238L1 8.35645L1.54492 7.8418L1.03906 7.30664L1.53809 6.79395L1 6.27148L0.999023 6.27051L2.5 4.72852L3.03809 5.25098L4.03809 4.22266L4.53906 3.70703L4.04492 3.18457L3.04492 2.12793L2.49902 2.64258L1 1.05664L1.3252 0.75H2.05762V0H5.14258V0.75H9.25684V0H12.3428V0.75H16.457V0H19.543V0.75H23.6572V0H26.7432V0.75H30.8574V0H33.9424V0.75H38.0576V0H41.1426V0.75H45.2568V0H48.3428V0.75H52.457V0H55.543V0.75H59.6572V0H62.7432V0.75H66.8574V0H69.9424V0.75H70.6748L70.999 1.05664L69.5 2.64258L68.9551 2.12793L67.9551 3.18457L67.4609 3.70703L67.9619 4.22266L68.9619 5.25098L69.499 4.72852Z';

/**
 * 웹 테이프 (원본 board.tsx: 84×34 칸 · 위 -16 · 가운데)
 * on: 붙은 테이프 74×26 (6, 5.23) · 불투명도 .95 / lift: 떼려고 올린 테이프 86×43 (0, -6.5) .85 + 그림자 / dash: 붙일 자리 점선 72×22 (6, 6)
 */
export function WebTape({ color, state }: { color: string; state: 'on' | 'lift' | 'dash' }) {
  if (state === 'on')
    return (
      <Svg width={74} height={26} viewBox="0 0 74 26" style={st.webOn}>
        <Path d={TAPE_ON} fill={color} opacity={0.95} />
      </Svg>
    );
  if (state === 'lift')
    return (
      <View style={st.webLift}>
        {/* 원본은 overflow visible (경로가 y -0.5 까지) → 위로 1 늘려서 그림 */}
        <Svg width={86} height={44} viewBox="0 -1 86 44">
          <Path d={TAPE_LIFT} fill={color} opacity={0.85} />
        </Svg>
      </View>
    );
  return (
    <Svg width={72} height={22} viewBox="0 0 72 22" style={st.webDash}>
      <Path d={TAPE_DASH} fill={color} fillOpacity={0.22} stroke={color} strokeWidth={1.5} strokeDasharray="4 3" />
    </Svg>
  );
}

const st = StyleSheet.create({
  appTape: { position: 'absolute', top: -8, left: '50%', marginLeft: -28, width: 57, height: 19, transform: [{ rotate: '-3deg' }] },
  webOn: { position: 'absolute', left: 6, top: 5.23 },
  /* 원본 drop-shadow(0 3px 6px rgba(0,0,0,.18)) */
  webLift: { position: 'absolute', left: 0, top: -7.5, shadowColor: '#000000', shadowOpacity: 0.18, shadowRadius: 6, shadowOffset: { width: 0, height: 3 }, elevation: 3 },
  webDash: { position: 'absolute', left: 6, top: 6 },
});
