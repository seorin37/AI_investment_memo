import React, { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MobileScreen } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { NewMemo } from '@/features/board/NewMemo';
import { mockNewMemoProps } from '@/features/board/NewMemo.mock';
import { splitMemo } from '@/lib/memoText';
import { useUI } from '@/store/ui';

/**
 * 새 메모 (아래에서 올라옴). 한 칸 글 → 저장할 때 웹과 같은 규칙: 첫 줄 trim = 제목, 나머지 = 본문 (lib/memoText.splitMemo).
 * mock 단계: 서버에 저장하지 않고 나눈 결과만 알림. AI 연결을 켰으면 AI 연결 화면으로.
 */
export default function NewMemoScreen() {
  const { name, first_line } = useLocalSearchParams<{ code?: string; name?: string; first_line?: string }>();
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  const [value, setValue] = useState(first_line ? `${first_line}\n` : '');
  const [aiLink, setAiLink] = useState(false);
  const done = () => {
    const { title, body } = splitMemo(value);
    if (aiLink) {
      router.replace({ pathname: '/memo/link', params: { title, body } });
      return;
    }
    toast(`저장했어요 (예시) · 제목 "${title}"${body ? ` · 본문 ${body.split('\n').length}줄` : ''}`);
    router.back();
  };
  return (
    <MobileScreen
      bg="#FFFFFF"
      bar={
        <TopBar
          left="cancel"
          title={`${name || '종목'} · 새 메모`}
          onCancel={() => router.back()}
          actions={[{ kind: 'text', label: '완료', emphasis: true, disabled: !value.trim(), onPress: done }]}
        />
      }
    >
      <NewMemo {...mockNewMemoProps} value={value} onChangeValue={setValue} ai_link={aiLink} onChangeAiLink={setAiLink} />
    </MobileScreen>
  );
}
