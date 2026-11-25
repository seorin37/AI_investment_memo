import React, { useState } from 'react';
import { Keyboard, View, type LayoutChangeEvent } from 'react-native';
import { useRouter } from 'expo-router';
import { create } from 'zustand';
import { chapterAt, fmt, useStudioPlayer } from '@/store/studioPlayer';
import { blockPlay } from '../appAudio';
import { epOf } from '../audioEp';
import { AppMiniPlayer } from './MiniPlayer';

/** 미니 플레이어 높이 · 아래 것과 간격 */
export const MINI_H = 62;
export const MINI_GAP = 8;
/** 떠 있을 때 본문 끝 · 떠 있는 버튼 · 스낵바가 비켜 주는 높이 */
const SPACE = MINI_H + MINI_GAP * 2;

/* 글을 쓰는 동안(키보드)에는 입력 칸을 가리지 않게 숨김 */
const useKb = create<{ on: boolean }>(() => ({ on: false }));
Keyboard.addListener('keyboardDidShow', () => useKb.setState({ on: true }));
Keyboard.addListener('keyboardDidHide', () => useKb.setState({ on: false }));

/** 미니 플레이어를 띄울 때인지 (듣는 중이거나 멈춰 둔 것이 있음) */
export function useMiniOn() {
  const on = useStudioPlayer((s) => (s.mini || s.playing) && s.made.some((m) => m.id === s.cur));
  return !useKb((s) => s.on) && on;
}
export const useMiniSpace = () => (useMiniOn() ? SPACE : 0);

/** 스크롤 본문 맨 끝에 두는 여백 */
export function MiniSpace() {
  return <View style={{ height: useMiniSpace() }} />;
}

/** 재생 상태에 이어진 미니 플레이어. bottom: 화면(또는 시트 틀) 바닥에서 */
export function MiniBar({ bottom, hidden = false, beforeOpen }: { bottom: number; hidden?: boolean; beforeOpen?: () => void }) {
  const router = useRouter();
  const on = useMiniOn();
  const p = useStudioPlayer();
  const item = p.made.find((m) => m.id === p.cur);
  const ep = epOf(item);
  const ch = ep.chapters[chapterAt(p.t, ep)][1].split(' ·')[0];
  return (
    <AppMiniPlayer
      visible={on && !hidden}
      bottom={bottom}
      title={item?.title ?? ''}
      sub={`${ch} · ${fmt(p.t)} / ${fmt(ep.dur)}`}
      progress={p.t / ep.dur}
      playing={p.playing}
      onOpen={() => {
        beforeOpen?.();
        router.push('/studio-player');
      }}
      onToggle={() => {
        if (blockPlay()) return;
        p.setMini(true); // 멈춰도 사라지지 않게
        p.toggle();
      }}
      onClose={p.closeMini}
    />
  );
}

/** 전체 높이 시트의 버튼 줄 바로 위 (자리를 차지함) */
export function MiniInline({ beforeOpen }: { beforeOpen?: () => void }) {
  if (!useMiniOn()) return null;
  return (
    <View style={{ height: MINI_H, marginBottom: MINI_GAP }}>
      <MiniBar bottom={0} beforeOpen={beforeOpen} />
    </View>
  );
}

/** 아래 시트 높이를 재서 그 위 8 */
export function useSheetMini() {
  const on = useMiniOn();
  const [h, setH] = useState(0);
  return { on, bottom: h + MINI_GAP, onLayout: (e: LayoutChangeEvent) => setH(e.nativeEvent.layout.height), room: on ? MINI_H + MINI_GAP * 2 : 0 };
}
