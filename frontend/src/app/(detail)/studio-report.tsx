import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { reportView, useWatchToMemo } from '@/ui/screens/studio/reportView';
import { AppReport } from '@/ui/screens/studio/app/Report';

/** 앱 주간보고서 (원본 studio.html pgRp). 고른 종목 · 증시 흐름 포함 여부는 만든 항목에서.
 *  '메모에 추가'(2026-11-24): 제안 내용으로 메모 쓰기 화면을 채워 열고, 저장하면 보고서에 '추가됨'을 남긴다 */
export default function StudioReportScreen() {
  const router = useRouter();
  const toMemo = useWatchToMemo();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curReport);
  if (Platform.OS === 'web') return <Redirect href="/report" />;
  const item = made.find((m) => m.id === cur && m.kind === 'report') ?? made.find((m) => m.kind === 'report');
  /* 서버 보고서면 그 내용, 아니면 mock 예시 (2026-11-23) */
  const v = reportView(item);
  return (
    <AppReport
      rep={v.rep}
      stocks={v.stocks}
      market={v.market}
      allDefault={v.allDefault}
      onBack={() => router.back()}
      onOpenMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      onWatch={(s, i) => toMemo(s, s.watch[i], item?.server ? item.id : undefined)}
    />
  );
}
