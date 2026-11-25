import React, { useState } from 'react';
import { Platform, View } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useStudioPlayer } from '@/store/studioPlayer';
import { Head } from '@/ui/screens/my/app/parts';
import { reportView } from '@/ui/screens/studio/reportView';
import { NewMemoSheet, type NewMemoTarget } from '@/ui/screens/memo/app/NewMemoSheet';
import { AppReportDetail } from '@/ui/screens/studio/app/ReportDetail';
import { webColor } from '@/ui/theme';

/** 앱 주간보고서 자세히 보기 (웹과 같은 내용 · 폰 폭). '메모에 추가'는 이동하지 않고 새 메모 시트를 채워 엶 (NewMemoSheet) */
export default function StudioReportScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [memoTo, setMemoTo] = useState<NewMemoTarget | null>(null);
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curReport);
  if (Platform.OS === 'web') return <Redirect href="/report" />;
  const item = made.find((m) => m.id === cur && m.kind === 'report') ?? made.find((m) => m.kind === 'report');
  const v = reportView(item);
  return (
    <View style={{ flex: 1, paddingTop: insets.top, paddingBottom: insets.bottom, backgroundColor: webColor.page }}>
      <Head title="AI 주간보고서" onBack={() => router.back()} />
      <AppReportDetail
        rep={v.rep}
        item={item}
        stocks={v.stocks}
        market={v.market}
        allDefault={v.allDefault}
        onMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
        onWatch={(s, w) => {
          const title = w.memo_title ?? w.text;
          setMemoTo({ code: s.stock_code, name: s.name, text: w.memo_body ? `${title}\n${w.memo_body}` : title, ai: true, studio: { itemId: item?.server ? item.id : undefined, key: w.sid ? `${s.stock_code}:${w.sid}` : undefined } });
        }}
        onOpenMemo={(_code, id) => router.push({ pathname: '/memo/[id]', params: { id } })}
      />
      <NewMemoSheet target={memoTo} onClose={() => setMemoTo(null)} />
    </View>
  );
}
