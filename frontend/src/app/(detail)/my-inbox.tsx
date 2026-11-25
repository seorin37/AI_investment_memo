import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { openMade } from '@/store/genJobs';
import { useMyMock } from '@/store/myMock';
import { useInboxData } from '@/ui/screens/my/useInboxData';
import { useStudioPlayer } from '@/store/studioPlayer';
import type { StudioKind } from '@/ui/screens/studio/Studio.types';
import { AppInbox } from '@/ui/screens/my/app/Inbox';

/** 알림에 항목 id 가 없어 설명 앞말로 종류를 알아내고, 그 종류의 가장 최근 결과를 엶 */
const KIND_OF: [string, StudioKind][] = [['오디오', 'audio'], ['주간보고서', 'report'], ['투자 실험실', 'lab']];

/** 앱 알림함 (원본 my.html inboxHTML · 홈 위쪽 종). 실제 모드면 내 종목 AI 업데이트와 서버 읽음 상태, mock 모드면 예시 (useInboxData) */
export default function MyInboxScreen() {
  const router = useRouter();
  const noti = useMyMock((s) => s.noti);
  const inbox = useInboxData();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppInbox
      items={inbox.items}
      unread={inbox.unread}
      noti={noti}
      onBack={() => router.back()}
      onOpen={(n) => {
        inbox.read(n.id);
        if (n.kind === 'ai' && n.memo_id) router.push({ pathname: '/memo/[id]', params: { id: n.memo_id, tab: 'ai' } });
        else if (n.kind === 'ai' && n.stock_code) router.push({ pathname: '/stocks/[code]', params: { code: n.stock_code } });
        else {
          const kind = KIND_OF.find(([t]) => n.sub.startsWith(t))?.[1];
          const item = useStudioPlayer.getState().made.find((m) => m.kind === kind);
          if (item) openMade(item);
          else router.navigate('/studio');
        }
      }}
      onReadAll={inbox.readAll}
      onSettings={() => router.push('/my-noti')}
    />
  );
}
