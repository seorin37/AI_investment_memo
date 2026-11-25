import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { reportView } from '@/ui/screens/studio/reportView';
import { useAddMemo } from '@/ui/screens/studio/useAddMemo';
import { AppReport } from '@/ui/screens/studio/app/Report';

/** 앱 주간보고서 (원본 studio.html pgRp). 고른 종목 · 증시 흐름 포함 여부는 만든 항목에서.
 *  '메모에 추가': 화면을 옮기지 않고 그 종목 메모로 바로 저장 (useAddMemo) */
export default function StudioReportScreen() {
  const router = useRouter();
  const memo = useAddMemo();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curReport);
  if (Platform.OS === 'web') return <Redirect href="/report" />;
  const item = made.find((m) => m.id === cur && m.kind === 'report') ?? made.find((m) => m.kind === 'report');
  /* 서버 보고서면 그 내용, 아니면 mock 예시 (2026-11-23) */
  const v = reportView(item);
  return (
    <AppReport
      rep={v.rep}
      stocks={v.stocks.map((s) => ({ ...s, watch: s.watch.map((w, i) => ({ ...w, added: w.added || memo.isAdded(item?.id, `${s.stock_code}:${w.sid ?? i}`) })) }))}
      market={v.market}
      allDefault={v.allDefault}
      onBack={() => router.back()}
      onOpenMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onWatch={(s, i) => {
        const w = s.watch[i];
        memo.add({ code: s.stock_code, title: w.memo_title ?? w.text, body: w.memo_body ?? '', itemId: item?.id, key: `${s.stock_code}:${w.sid ?? i}`, server: item?.server && !!w.sid });
      }}
    />
  );
}
