import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockReport, mockReportStocks } from '@/ui/screens/studio/Studio.mock';
import { WebReportDetail } from '@/ui/screens/studio/web/Report';

/** 웹 주간보고서 자세히 보기 (가운데 860 · 원본 screens/report.tsx). 앱은 스튜디오 › 주간보고서 화면 */
export default function ReportScreen() {
  const router = useRouter();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curReport);
  if (Platform.OS !== 'web') return <Redirect href="/studio-report" />;
  const item = made.find((m) => m.id === cur && m.kind === 'report') ?? made.find((m) => m.kind === 'report');
  const stocks = mockReportStocks.filter((s) => (item?.codes ?? []).includes(s.stock_code));
  return (
    <WebReportDetail
      rep={mockReport}
      item={item}
      stocks={stocks}
      market={!!item?.market}
      allDefault={stocks.length === mockReportStocks.length}
      onMemo={(code) => router.navigate({ pathname: '/stocks/[code]', params: { code } })}
    />
  );
}
