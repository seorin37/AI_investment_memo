import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { useUI } from '@/store/ui';
import { reportView } from '@/ui/screens/studio/reportView';
import { AppReport } from '@/ui/screens/studio/app/Report';

/** 앱 주간보고서 (원본 studio.html pgRp). 고른 종목 · 증시 흐름 포함 여부는 만든 항목에서. '메모에 추가'는 연결 안 됨 → 안내만 */
export default function StudioReportScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
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
      onWatch={() => toast('아직 연결되지 않았어요 · 데이터는 그대로예요')}
    />
  );
}
