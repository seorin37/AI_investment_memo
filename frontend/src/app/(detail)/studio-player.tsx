import React from 'react';
import { BackHandler, Platform } from 'react-native';
import { Redirect, useFocusEffect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { blockPlay } from '@/ui/screens/studio/appAudio';
import { epOf } from '@/ui/screens/studio/audioEp';
import { AppPlayer, SPEEDS } from '@/ui/screens/studio/app/Player';

/** 앱 오디오 플레이어 (원본 studio.html pgPl). 앱은 아직 소리 없이 타이머 (서버 오디오면 그 편의 대본·챕터). 나가면 듣던 중일 때 미니 플레이어로 */
export default function StudioPlayerScreen() {
  const router = useRouter();
  const p = useStudioPlayer();
  const item = p.made.find((m) => m.id === p.cur) ?? p.made.find((m) => m.kind === 'audio');
  const back = () => { p.leavePlayer(); router.back(); };
  useFocusEffect(
    React.useCallback(() => {
      const sub = BackHandler.addEventListener('hardwareBackPress', () => { useStudioPlayer.getState().leavePlayer(); return false; });
      return () => sub.remove();
    }, []),
  );
  if (Platform.OS === 'web') return <Redirect href="/" />;
  if (!item) return null;
  return (
    <AppPlayer
      item={item}
      ep={epOf(item)}
      t={p.cur === item.id ? p.t : 0}
      playing={p.cur === item.id && p.playing}
      speed={p.speed}
      onBack={back}
      onToggle={() => !blockPlay() && (p.cur === item.id ? p.toggle() : p.play(item.id, true))}
      onSeek={(t) => { if (p.cur !== item.id) p.select(item.id); p.seek(t); }}
      onSpeed={() => p.nextSpeed(SPEEDS)}
      onOpenMemo={() => {
        const ml = epOf(item).memo_link as { memo_id?: string } | null;
        const code = item.codes?.[0] ?? '000660';
        if (ml?.memo_id) router.push({ pathname: '/memo/[id]', params: { id: ml.memo_id, tab: 'ai' } });
        else router.push({ pathname: '/stocks/[code]', params: { code } });
      }}
      onRemake={() => { p.leavePlayer(); router.navigate({ pathname: '/studio', params: { make: 'audio' } }); }}
    />
  );
}
