import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useMyMock } from '@/store/myMock';
import { mockInbox } from '@/ui/screens/my/My.mock';
import { AppInbox } from '@/ui/screens/my/app/Inbox';

/** 앱 알림함 (원본 my.html inboxHTML · 홈 위쪽 종). 읽음은 화면 상태(mock)만 */
export default function MyInboxScreen() {
  const router = useRouter();
  const noti = useMyMock((s) => s.noti);
  const unread = useMyMock((s) => s.unread);
  const read = useMyMock((s) => s.read);
  const readAll = useMyMock((s) => s.readAll);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppInbox
      items={mockInbox}
      unread={unread}
      noti={noti}
      onBack={() => router.back()}
      onOpen={(n) => {
        read(n.id);
        if (n.kind === 'ai' && n.stock_code) router.push({ pathname: '/stocks/[code]', params: { code: n.stock_code } });
        else router.navigate('/studio');
      }}
      onReadAll={readAll}
      onSettings={() => router.push('/my-noti')}
    />
  );
}
