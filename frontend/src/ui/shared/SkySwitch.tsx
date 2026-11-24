import React from 'react';
import { Pressable } from 'react-native';
import Svg, { Circle, ClipPath, Defs, G, LinearGradient, RadialGradient, Rect, Stop } from 'react-native-svg';
import { Keep } from './Dark';

/**
 * 낮·밤 하늘 스위치 (Lucian #021 · MIT (c) 2026 Seokwoooo) — 원본 224×94 를 그대로 그리고 크기만 줄임
 * 웹 사이드바 48×20 (×.2143) · 앱 MY 64×27 (×.2857).
 * 이번 묶음은 낮/밤 두 상태 모양만. 바뀌는 움직임(해가 달로 굴러감 · 구름·별)은 ⑩ 다크 모드 묶음에서.
 * 원본과 다른 곳: 안쪽 그림자(inset)는 RN에 없어 뺌.
 */
export function SkySwitch({ on, onToggle, width = 48, label = '다크 모드' }: { on: boolean; onToggle?: () => void; width?: number; label?: string }) {
  const h = (width * 94) / 224;
  return (
    <Pressable onPress={onToggle} accessibilityRole="switch" accessibilityState={{ checked: on }} accessibilityLabel={label} hitSlop={12}>
      <Keep>
      <Svg width={width} height={h} viewBox="0 0 224 94">
        <Defs>
          <ClipPath id="u021c">
            <Rect x="0" y="0" width="224" height="94" rx="47" />
          </ClipPath>
          <LinearGradient id="u021d" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#5DB7FF" />
            <Stop offset="1" stopColor="#9ED8FF" />
          </LinearGradient>
          <LinearGradient id="u021n" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#141A3A" />
            <Stop offset="1" stopColor="#232C5C" />
          </LinearGradient>
          <RadialGradient id="u021s" cx="0.35" cy="0.3" r="0.75" fx="0.35" fy="0.3">
            <Stop offset="0" stopColor="#FFF1A8" />
            <Stop offset="0.45" stopColor="#FFD23F" />
            <Stop offset="1" stopColor="#F8A91E" />
          </RadialGradient>
          <RadialGradient id="u021m" cx="0.35" cy="0.3" r="0.75" fx="0.35" fy="0.3">
            <Stop offset="0" stopColor="#F4F6FB" />
            <Stop offset="0.6" stopColor="#C9CFDD" />
            <Stop offset="1" stopColor="#A9B0C2" />
          </RadialGradient>
        </Defs>
        <G clipPath="url(#u021c)">
          <Rect x="0" y="0" width="224" height="94" fill={on ? 'url(#u021n)' : 'url(#u021d)'} />
          {/* 해 둘레 빛 (halo): 가운데 (47,47) → 밤엔 130 오른쪽 */}
          <G x={on ? 130 : 0}>
            <Circle cx="47" cy="47" r="111" fill="rgba(255,255,255,0.12)" />
            <Circle cx="47" cy="47" r="88" fill="rgba(255,255,255,0.12)" />
            <Circle cx="47" cy="47" r="65" fill="rgba(255,255,255,0.12)" />
          </G>
          {on ? (
            <G>
              {[
                [30, 20, 4],
                [58, 56, 3],
                [86, 26, 4],
                [44, 72, 3],
                [110, 60, 2],
                [20, 46, 2],
              ].map(([x, y, s]) => (
                <Circle key={`${x}-${y}`} cx={x + s / 2} cy={y + s / 2} r={s / 2} fill="#FFFFFF" />
              ))}
            </G>
          ) : (
            <G>
              {/* 구름 2 (뒤) + 그림자 복사본 */}
              <Rect x="72" y="86" width="80" height="36" rx="18" fill="#E3F1FF" />
              <Rect x="108" y="72" width="96" height="52" rx="26" fill="#E3F1FF" />
              {/* 구름 1 + 그림자 복사본 2개 */}
              <Rect x="44" y="84" width="100" height="36" rx="18" fill="#FFFFFF" />
              <Rect x="74" y="70" width="108" height="44" rx="22" fill="#FFFFFF" />
              <Rect x="114" y="56" width="120" height="56" rx="28" fill="#FFFFFF" />
            </G>
          )}
          {/* 손잡이: 해 (밤엔 130 오른쪽 · 달) */}
          <G x={on ? 130 : 0}>
            <Circle cx="47" cy="47" r="39" fill={on ? 'url(#u021m)' : 'url(#u021s)'} />
            {on && (
              <G>
                <Circle cx="38" cy="34" r="10" fill="#A3AABC" />
                <Circle cx="61" cy="55" r="7" fill="#A3AABC" />
                <Circle cx="36.5" cy="60.5" r="4.5" fill="#A3AABC" />
              </G>
            )}
          </G>
        </G>
      </Svg>
      </Keep>
    </Pressable>
  );
}
