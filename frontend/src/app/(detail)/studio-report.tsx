import React, { useState } from 'react';
import { Platform, View } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { reportView } from '@/ui/screens/studio/reportView';
import { NewMemoSheet, type NewMemoTarget } from '@/ui/screens/memo/app/NewMemoSheet';
import { AppReport } from '@/ui/screens/studio/app/Report';

/** 앱 주간보고서 (원본 studio.html pgRp). 고른 종목 · 증시 흐름 포함 여부는 만든 항목에서.
 *  '메모에 추가': 이동하지 않고 새 메모 시트를 채워 엶 (NewMemoSheet) */
export default function StudioReportScreen() {
  const router = useRouter();
  const [memoTo, setMemoTo] = useState<NewMemoTarget | null>(null);
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curReport);
  if (Platform.OS === 'web') return <Redirect href="/report" />;
  const item = made.find((m) => m.id === cur && m.kind === 'report') ?? made.find((m) => m.kind === 'report');
  /* 서버 보고서면 그 내용, 아니면 mock 예시 (2026-11-23) */
  const v = reportView(item);
  return (
    <View style={{ flex: 1 }}>
    <AppReport
      title={item?.title ?? '주간보고서'}
      rep={v.rep}
      stocks={v.stocks}
      market={v.market}
      allDefault={v.allDefault}
      onBack={() => router.back()}
      onOpenMemo={(code, memoId) => (memoId ? router.push({ pathname: '/memo/[id]', params: { id: memoId } }) : router.push({ pathname: '/stocks/[code]', params: { code } }))}
      onWatch={(s, i) => {
        const w = s.watch[i];
        const title = w.memo_title ?? w.text;
        setMemoTo({ code: s.stock_code, name: s.name, text: w.memo_body ? `${title}\n${w.memo_body}` : title, ai: true, studio: { itemId: item?.server ? item.id : undefined, key: w.sid ? `${s.stock_code}:${w.sid}` : undefined } });
      }}
    />
    <NewMemoSheet target={memoTo} onClose={() => setMemoTo(null)} />
    </View>
  );
}
