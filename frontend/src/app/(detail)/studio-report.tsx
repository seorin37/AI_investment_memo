import React from 'react';
import { Platform, View } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useStudioPlayer } from '@/store/studioPlayer';
import { Head } from '@/ui/screens/my/app/parts';
import { reportView } from '@/ui/screens/studio/reportView';
import { useAddMemo } from '@/ui/screens/studio/useAddMemo';
import { WebReportDetail } from '@/ui/screens/studio/web/Report';
import { webColor } from '@/ui/theme';

/** 앱 주간보고서 자세히 보기 = 웹 WebReportDetail (폰 폭). '메모에 추가'는 화면을 옮기지 않고 그 종목 메모로 바로 저장 (useAddMemo) */
export default function StudioReportScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const memo = useAddMemo();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curReport);
  if (Platform.OS === 'web') return <Redirect href="/report" />;
  const item = made.find((m) => m.id === cur && m.kind === 'report') ?? made.find((m) => m.kind === 'report');
  const v = reportView(item);
  const stocks = v.stocks.map((s) => ({ ...s, watch: s.watch.map((w, i) => ({ ...w, added: w.added || memo.isAdded(item?.id, `${s.stock_code}:${w.sid ?? i}`) })) }));
  return (
    <View style={{ flex: 1, paddingTop: insets.top, paddingBottom: insets.bottom, backgroundColor: webColor.page }}>
      <Head title="AI 주간보고서" onBack={() => router.back()} />
      <WebReportDetail
        mobile
        rep={v.rep}
        item={item}
        stocks={stocks}
        market={v.market}
        allDefault={v.allDefault}
        onMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
        onWatch={(s, w) => {
          const i = s.watch.indexOf(w);
          memo.add({ code: s.stock_code, title: w.memo_title ?? w.text, body: w.memo_body ?? '', itemId: item?.id, key: `${s.stock_code}:${w.sid ?? i}`, server: item?.server && !!w.sid });
        }}
        onOpenMemo={(_code, id) => router.push({ pathname: '/memo/[id]', params: { id } })}
      />
    </View>
  );
}
