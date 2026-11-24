import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { AppTrash } from '@/ui/screens/my/app/Trash';
import { useTrashData } from '@/ui/screens/my/useTrashData';

/** 앱 MY › 휴지통 (원본 my.html openTrash). 데이터: useTrashData (실제 GET /trash · mock 이면 store/myMock) */
export default function MyTrashScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const trash = useTrashData(() => toast('아직 연결되지 않았어요 · 데이터는 그대로예요'));
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppTrash
      items={trash.items}
      onBack={() => router.back()}
      onRestore={(t) => trash.restore(t)}
      onUndo={trash.undo}
      onPurge={trash.purge}
    />
  );
}
