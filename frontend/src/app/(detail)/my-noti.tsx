import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useMyMock } from '@/store/myMock';
import { useUI } from '@/store/ui';
import { AppNoti } from '@/ui/screens/my/app/Noti';

/** 앱 MY › 알림 (원본 my.html openNoti). 화면 상태만 — 서버 저장·OS 알림 권한 없음 */
export default function MyNotiScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const noti = useMyMock((s) => s.noti);
  const setNoti = useMyMock((s) => s.setNoti);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppNoti
      noti={noti}
      onBack={() => router.back()}
      onChange={(n) => {
        const on = n.ai !== noti.ai ? n.ai : n.studio;
        setNoti(n);
        toast(on ? '알림을 켰어요 · 알림함에 다시 보여요' : '알림을 껐어요 · 알림함에서도 안 보여요');
      }}
    />
  );
}
