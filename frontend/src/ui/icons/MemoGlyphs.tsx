import React from 'react';
import Svg, { Circle, G, Path, Rect } from 'react-native-svg';

/* 메모 상세·새 메모·AI 연결 아이콘 — 원본 앱 memo.html · 웹 board.tsx / memox.tsx 의 SVG 그대로 */

type C = { color?: string; size?: number };
const svgStyle = { flexShrink: 0 } as const;

/** 앱 뒤로 (원본 #back: 22 · M15 5l-7 7 7 7 · 2.2) */
export function BackChevron({ color = '#16171A', size = 22 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={svgStyle}>
      <Path d="M15 5l-7 7 7 7" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 앱 ⋯ 가로 (원본 #dmore: 22 · 점 r1.7) */
export function DotsH({ color = '#16171A', size = 22 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color} style={svgStyle}>
      <Circle cx={5} cy={12} r={1.7} />
      <Circle cx={12} cy={12} r={1.7} />
      <Circle cx={19} cy={12} r={1.7} />
    </Svg>
  );
}

/** 앱 닫기 × (원본 #aix: 20 · 2.2) */
export function CloseX({ color = '#16171A', size = 20, stroke = 2.2 }: C & { stroke?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={svgStyle}>
      <Path d="M6 6l12 12M18 6 6 18" stroke={color} strokeWidth={stroke} strokeLinecap="round" />
    </Svg>
  );
}

/** 앱 펼치기 화살 (원본 CHV: 12 · 1.6) */
export function Chev12({ color = '#575B63' }: C) {
  return (
    <Svg width={12} height={12} viewBox="0 0 12 12" fill="none" style={svgStyle}>
      <Path d="M3 4.5 6 7.5 9 4.5" stroke={color} strokeWidth={1.6} />
    </Svg>
  );
}

/** 앱 소식 종류 그림 (원본 FK: 18 · 2) */
export function FeedKindIcon({ kind, color }: { kind: '뉴스' | '공시' | '주가'; color: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" style={svgStyle}>
      {kind === '뉴스' ? (
        <>
          <Rect x={4} y={4} width={16} height={16} rx={3} />
          <Path d="M8 9h8M8 13h8M8 17h5" />
        </>
      ) : kind === '공시' ? (
        <>
          <Path d="M6 3h8l4 4v14H6z" />
          <Path d="M9 12h6M9 16h6" />
        </>
      ) : (
        <Path d="M4 18l5-6 4 3 7-8M4 21h16" />
      )}
    </Svg>
  );
}

/** 앱 메모 기록: 고침 (ICP) · 첫 메모 (ICN) — 16 */
export function RevIcon({ first, color = '#6A42AB', size = 16 }: C & { first: boolean }) {
  return first ? (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} style={svgStyle}>
      <Path d="M5 4h14v11l-5 5H5z" />
    </Svg>
  ) : (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.1} strokeLinecap="round" strokeLinejoin="round" style={svgStyle}>
      <Path d="M4 20h4L19 9l-4-4L4 16z" />
    </Svg>
  );
}

/** 앱 시트 '수정 이력 보기' 시계 (20 · 1.8) */
export function ClockIcon({ color, size = 20 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" style={svgStyle}>
      <Circle cx={12} cy={12} r={9} />
      <Path d="M12 7v5l3 2" />
    </Svg>
  );
}

/** 앱 항목 없음 돋보기 (원본 .emp .ic2: 22 #9A9EA7) */
export function SearchGlass({ color = '#9A9EA7', size = 22 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" style={svgStyle}>
      <Circle cx={11} cy={11} r={7} />
      <Path d="M20 20l-4-4" />
    </Svg>
  );
}

/** 앱 연결 완료 체크 (원본 .done2: 38 흰 2.6) */
export function DoneCheck({ size = 38 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" style={svgStyle}>
      <Path d="M5 12.5l4.5 4.5L19 7.5" />
    </Svg>
  );
}

/** 넛지 반짝 (원본 .mnudge · 웹 Spark: 18 흰) */
export function NudgeSpark({ size = 18 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 19 19" fill="none" style={svgStyle}>
      <Path d="M8.70834 2.375C9.18334 5.77917 10.8458 7.44167 14.25 7.91667C10.8458 8.39167 9.18334 10.0542 8.70834 13.4583C8.23334 10.0542 6.57084 8.39167 3.16667 7.91667C6.57084 7.44167 8.23334 5.77917 8.70834 2.375Z" fill="white" />
      <Path d="M15.0417 11.875C15.2792 13.5771 16.1104 14.4083 17.8125 14.6458C16.1104 14.8833 15.2792 15.7146 15.0417 17.4167C14.8042 15.7146 13.9729 14.8833 12.2708 14.6458C13.9729 14.4083 14.8042 13.5771 15.0417 11.875Z" fill="white" />
    </Svg>
  );
}
export function NudgeArrow({ size = 16 }: C) {
  return (
    <Svg width={size} height={size} viewBox="0 0 14 14" fill="none" style={svgStyle}>
      <Path d="M3 7h8M7.5 3.5 11 7l-3.5 3.5" stroke="white" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}
export function NudgeCross() {
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14" fill="none" style={svgStyle}>
      <Path d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5" stroke="white" strokeOpacity={0.7} strokeWidth={1.6} strokeLinecap="round" />
    </Svg>
  );
}

/** 체크 (12 · 1.8) — 웹 단계 알약 · 항목 동그라미 · 웹 토글 */
export function TickSmall({ color = 'white', size = 12, stroke = 1.8 }: C & { stroke?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 12 12" fill="none" style={svgStyle}>
      <Path d="M2.5 6L4.8 8.3L9.5 3.5" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/* ───────── 웹 (board.tsx) ───────── */

/** 웹 소식 종류 그림 (KIND: 18 · viewBox 18) */
export function WebKindIcon({ kind }: { kind: '뉴스' | '공시' | '주가' }) {
  if (kind === '뉴스')
    return (
      <Svg width={18} height={18} viewBox="0 0 18 18" fill="none" style={svgStyle}>
        <Path d="M2.25 8.25L13.5 4.5V13.5L2.25 10.5V8.25Z" stroke="#3D73F0" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        <Path
          d="M8.6998 12.6004C8.621 12.886 8.48672 13.1533 8.30462 13.3871C8.12253 13.6208 7.89617 13.8164 7.63849 13.9626C7.38081 14.1089 7.09684 14.2029 6.80281 14.2394C6.50877 14.2759 6.21042 14.2542 5.9248 14.1754C5.63917 14.0966 5.37186 13.9623 5.13813 13.7802C4.9044 13.5981 4.70883 13.3718 4.56257 13.1141C4.41632 12.8564 4.32226 12.5724 4.28575 12.2784C4.24924 11.9844 4.271 11.686 4.3498 11.4004"
          stroke="#3D73F0"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <Path d="M15.75 6.75V11.25" stroke="#3D73F0" strokeWidth={1.5} strokeLinecap="round" />
      </Svg>
    );
  if (kind === '주가')
    return (
      <Svg width={18} height={18} viewBox="0 0 18 18" fill="none" style={svgStyle}>
        <G stroke="#C98A0B" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M9 11.5V14.625" />
          <Path d="M11.5 10.6494V14.625" />
          <Path d="M14 8.16016V14.6252" />
          <Path d="M15.25 3.375L9.84625 8.77875C9.81722 8.80785 9.78274 8.83094 9.74477 8.8467C9.70681 8.86245 9.6661 8.87056 9.625 8.87056C9.5839 8.87056 9.54319 8.86245 9.50523 8.8467C9.46726 8.83094 9.43278 8.80785 9.40375 8.77875L7.34625 6.72125C7.28765 6.66267 7.20818 6.62975 7.12531 6.62975C7.04245 6.62975 6.96298 6.66267 6.90438 6.72125L2.75 10.875" />
          <Path d="M4 13.0391V14.6247" />
          <Path d="M6.5 10.6602V14.6252" />
        </G>
      </Svg>
    );
  return (
    <Svg width={18} height={18} viewBox="0 0 18 18" fill="none" style={svgStyle}>
      <G stroke="#7046F5" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <Path d="M5.25 15.25C4.91848 15.25 4.60054 15.1183 4.36612 14.8839C4.1317 14.6495 4 14.3315 4 14V4C4 3.66848 4.1317 3.35054 4.36612 3.11612C4.60054 2.8817 4.91848 2.75 5.25 2.75H10.25C10.4478 2.74968 10.6438 2.7885 10.8266 2.86423C11.0094 2.93996 11.1754 3.0511 11.315 3.19125L13.5575 5.43375C13.698 5.57344 13.8095 5.73959 13.8854 5.9226C13.9614 6.10561 14.0003 6.30186 14 6.5V14C14 14.3315 13.8683 14.6495 13.6339 14.8839C13.3995 15.1183 13.0815 15.25 12.75 15.25H5.25Z" />
        <Path d="M10.25 2.75V5.875C10.25 6.04076 10.3158 6.19973 10.4331 6.31694C10.5503 6.43415 10.7092 6.5 10.875 6.5H14" />
        <Path d="M7.75 7.125H6.5" />
        <Path d="M11.5 9.625H6.5" />
        <Path d="M11.5 12.125H6.5" />
      </G>
    </Svg>
  );
}

/** 웹 펼치기 화살 (Chev: 14 · #575B63 · 2) */
export function WebChev14({ up }: { up?: boolean }) {
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14" fill="none" style={[svgStyle, up ? { transform: [{ rotate: '180deg' }] } : null]}>
      <Path d="M4.08398 5.54199L7.00065 8.45866L9.91732 5.54199" stroke="#575B63" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 웹 메모 기록 그림: 고침 · 첫 메모 (16 · #575B63 · 2) */
export function WebRevIcon({ first }: { first: boolean }) {
  return first ? (
    <Svg width={16} height={16} viewBox="0 0 16 16" fill="none" stroke="#575B63" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={svgStyle}>
      <Path d="M13 6.33334C13.0004 6.15729 12.966 5.98289 12.8987 5.82022C12.8314 5.65755 12.7325 5.50982 12.6078 5.38556L10.6144 3.39223C10.4902 3.26752 10.3425 3.16865 10.1798 3.10133C10.0171 3.03401 9.84272 2.99957 9.66667 3H4.11111C3.81643 3 3.53381 3.11707 3.32544 3.32544C3.11706 3.53381 3 3.81643 3 4.11112V11.8889C3 12.1836 3.11706 12.4662 3.32544 12.6746C3.53381 12.8829 3.81643 13 4.11111 13H11.8889C12.1836 13 12.4662 12.8829 12.6746 12.6746C12.8829 12.4662 13 12.1836 13 11.8889V6.33334Z" />
      <Path d="M9.66602 3V5.77778C9.66602 5.92512 9.72455 6.06643 9.82873 6.17061C9.93292 6.2748 10.0742 6.33333 10.2216 6.33333H12.9993" />
    </Svg>
  ) : (
    <Svg width={16} height={16} viewBox="0 0 16 16" fill="none" stroke="#575B63" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={svgStyle}>
      <Path d="M8 3H4.11111C3.81643 3 3.53381 3.11706 3.32544 3.32544C3.11706 3.53381 3 3.81643 3 4.11111V11.8889C3 12.1836 3.11706 12.4662 3.32544 12.6746C3.53381 12.8829 3.81643 13 4.11111 13H11.8889C12.1836 13 12.4662 12.8829 12.6746 12.6746C12.8829 12.4662 13 12.1836 13 11.8889V8" />
      <Path d="M11.5415 2.79147C11.7625 2.57045 12.0623 2.44629 12.3748 2.44629C12.6874 2.44629 12.9872 2.57045 13.2082 2.79147C13.4292 3.01248 13.5533 3.31224 13.5533 3.6248C13.5533 3.93736 13.4292 4.23712 13.2082 4.45813L8.20095 9.46591C8.06903 9.59772 7.90606 9.6942 7.72706 9.74647L6.13095 10.2131C6.08314 10.2271 6.03247 10.2279 5.98423 10.2156C5.93599 10.2032 5.89196 10.1781 5.85675 10.1429C5.82154 10.1077 5.79644 10.0636 5.78408 10.0154C5.77172 9.96717 5.77256 9.91649 5.7865 9.86869L6.25317 8.27258C6.30568 8.09372 6.40235 7.93094 6.53428 7.79925L11.5415 2.79147Z" />
    </Svg>
  );
}

/** 웹 이어지는 흐름 화살 (20 · #9AA3B2) */
export function WebThreadArrow() {
  return (
    <Svg width={20} height={20} viewBox="0 0 20 20" fill="none" style={svgStyle}>
      <Path d="M4 10H16M11 5L16 10L11 15" stroke="#9AA3B2" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** 웹 'AI 가 요약했어요' 반짝 (14 · #747D8D) */
export function WebSparkle14() {
  return (
    <Svg width={14} height={14} viewBox="0 0 14 14" fill="none" stroke="#747D8D" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={svgStyle}>
      <Path d="M6.52212 2.53455C6.54295 2.42304 6.60212 2.32233 6.68939 2.24985C6.77666 2.17737 6.88653 2.1377 6.99997 2.1377C7.11341 2.1377 7.22328 2.17737 7.31055 2.24985C7.39782 2.32233 7.45699 2.42304 7.47782 2.53455L7.98872 5.23636C8.02501 5.42845 8.11835 5.60513 8.25658 5.74336C8.39481 5.88159 8.5715 5.97493 8.76358 6.01122L11.4654 6.52212C11.5769 6.54295 11.6776 6.60212 11.7501 6.68939C11.8226 6.77666 11.8622 6.88653 11.8622 6.99997C11.8622 7.11341 11.8226 7.22328 11.7501 7.31055C11.6776 7.39782 11.5769 7.45699 11.4654 7.47782L8.76358 7.98872C8.5715 8.02501 8.39481 8.11835 8.25658 8.25658C8.11835 8.39481 8.02501 8.5715 7.98872 8.76358L7.47782 11.4654C7.45699 11.5769 7.39782 11.6776 7.31055 11.7501C7.22328 11.8226 7.11341 11.8622 6.99997 11.8622C6.88653 11.8622 6.77666 11.8226 6.68939 11.7501C6.60212 11.6776 6.54295 11.5769 6.52212 11.4654L6.01122 8.76358C5.97493 8.5715 5.88159 8.39481 5.74336 8.25658C5.60513 8.11835 5.42845 8.02501 5.23636 7.98872L2.53455 7.47782C2.42304 7.45699 2.32233 7.39782 2.24985 7.31055C2.17737 7.22328 2.1377 7.11341 2.1377 6.99997C2.1377 6.88653 2.17737 6.77666 2.24985 6.68939C2.32233 6.60212 2.42304 6.54295 2.53455 6.52212L5.23636 6.01122C5.42845 5.97493 5.60513 5.88159 5.74336 5.74336C5.88159 5.60513 5.97493 5.42845 6.01122 5.23636L6.52212 2.53455Z" />
      <Path d="M10.8896 2.13965V4.08409" />
      <Path d="M11.8614 3.11133H9.91699" />
      <Path d="M3.11187 11.8614C3.64881 11.8614 4.08409 11.4262 4.08409 10.8892C4.08409 10.3523 3.64881 9.91699 3.11187 9.91699C2.57493 9.91699 2.13965 10.3523 2.13965 10.8892C2.13965 11.4262 2.57493 11.8614 3.11187 11.8614Z" />
    </Svg>
  );
}

/** 웹 AI 연결 토글 손잡이 안 그림 (Toggle45: 켬 체크 · 끔 ×, 10) */
export function Toggle45Mark({ on }: { on: boolean }) {
  return on ? (
    <Svg width={10} height={10} viewBox="0 0 10 10" fill="none" style={svgStyle}>
      <Path d="M2.29163 5.20801L4.16663 7.08301L7.70829 3.33301" stroke="#14171C" strokeWidth={1.66667} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  ) : (
    <Svg width={10} height={10} viewBox="0 0 10 10" fill="none" style={svgStyle}>
      <Path d="M3.125 3.125L6.875 6.875M6.875 3.125L3.125 6.875" stroke="#9AA3B2" strokeWidth={1.66667} strokeLinecap="round" />
    </Svg>
  );
}
