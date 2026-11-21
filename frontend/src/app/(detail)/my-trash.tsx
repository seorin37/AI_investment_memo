import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useMyMock } from '@/store/myMock';
import { useUI } from '@/store/ui';
import { AppTrash } from '@/ui/screens/my/app/Trash';

/** 앱 MY › 휴지통 (원본 my.html openTrash). 복원은 mock 휴지통에서 빼기 · 영구 삭제는 확인까지만 */
export default function MyTrashScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const trash = useMyMock((s) => s.trash);
  const restore = useMyMock((s) => s.restore);
  const undo = useMyMock((s) => s.undoRestore);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppTrash
      items={trash}
      onBack={() => router.back()}
      onRestore={(t) => restore(t.id)}
      onUndo={undo}
      onPurge={() => toast('아직 연결되지 않았어요 · 데이터는 그대로예요')}
    />
  );
}
