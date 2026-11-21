/* UI v2 공통 부품 확인 화면 — 개발 중(__DEV__)에만 열림. 4단계에서 삭제 예정 */
import React, { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { Redirect } from 'expo-router';
import { Text } from '@/components/ui/AppText';
import { AppIcon, Logo, WebIcon } from '@/ui/icons/Icon';
import { APP_ICONS } from '@/ui/icons/appIcons.data';
import { WEB_ICONS } from '@/ui/icons/webIcons.data';
import { TopBar } from '@/ui/layout/app/TopBar';
import { Odometer } from '@/ui/motion/Numbers';
import { Skeleton } from '@/ui/motion/Skeleton';
import { CheckBox } from '@/ui/shared/CheckBox';
import { AppChips, WebChips } from '@/ui/shared/Chips';
import { ConfirmDialog } from '@/ui/shared/ConfirmDialog';
import { Fab } from '@/ui/shared/Fab';
import { KindTag } from '@/ui/shared/KindTag';
import { Seg } from '@/ui/shared/Seg';
import { Sheet } from '@/ui/shared/Sheet';
import { AppSnackbar, WebSnackbar } from '@/ui/shared/Snackbar';
import { AppStockCard, WebStockHead } from '@/ui/shared/StockHead';
import { Toggle } from '@/ui/shared/Toggle';
import { AppViewToggle, WebViewToggle } from '@/ui/shared/ViewToggle';
import { appColor } from '@/ui/theme';

const SK = { stock_code: '000660', name: 'SK하이닉스', market: 'KOSPI' as const, status: 'holding' as const, logo: 'S', logo_bg: '#EA002C', price: 180500, change: 4200, change_pct: 2.38, as_of: '11.18', closes: [170, 168, 172, 171, 175, 177, 176, 180, 178, 182, 181, 185, 184, 186] };

export default function UiV2Check() {
  if (!__DEV__) return <Redirect href="/" />;
  return <Check />;
}

function Check() {
  const [seg, setSeg] = useState<'a' | 'b'>('a');
  const [chip, setChip] = useState<'all' | 'ai' | 'new'>('all');
  const [on, setOn] = useState(true);
  const [sheet, setSheet] = useState(false);
  const [dlg, setDlg] = useState(false);
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const [n, setN] = useState(5);
  return (
    <View style={{ flex: 1, backgroundColor: appColor.bg }}>
      <TopBar preset="updates" title="최신 업데이트" actions={[{ icon: 'checkAll', label: '모두 읽음' }, { icon: 'searchSm', label: '검색' }, { icon: 'bell', label: '알림' }]} avatar={{ name: '김나라' }} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }}>
        <Logo kind="app" size={110} />
        <AppStockCard {...SK} />
        <WebStockHead {...SK} />
        <Seg variant="appBoard" value={seg} onChange={setSeg} options={[{ key: 'a', label: '메모 보드' }, { key: 'b', label: '기업정보' }]} />
        <Seg variant="appDetail" value={seg} onChange={setSeg} options={[{ key: 'a', label: '메모' }, { key: 'b', label: 'AI 업데이트', count: 2 }]} />
        <Seg variant="web" value={seg} onChange={setSeg} options={[{ key: 'a', label: '연간' }, { key: 'b', label: '분기' }]} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <AppChips value={chip} onChange={setChip} options={[{ key: 'all', label: '전체' }, { key: 'ai', label: 'AI 연결' }, { key: 'new', label: '새 소식', dot: true, count: 3 }]} />
          <AppViewToggle value={view} onChange={setView} />
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FDFDFD', padding: 8 }}>
          <WebChips value={chip} onChange={setChip} options={[{ key: 'all', label: '전체' }, { key: 'ai', label: 'AI 연결', count: 3 }, { key: 'new', label: '새 소식', dot: true, count: 2 }]} />
          <WebViewToggle value={view} onChange={setView} />
        </View>
        <View style={{ flexDirection: 'row', gap: 16, alignItems: 'center' }}>
          <Toggle variant="app" on={on} onChange={setOn} label="AI 연결" />
          <Toggle variant="web" on={on} onChange={setOn} label="AI 연결" />
          <CheckBox variant="app" on={on} onChange={setOn} />
          <CheckBox variant="web" on={on} onChange={setOn} />
          <KindTag kind="공시" variant="app" />
          <KindTag kind="뉴스" variant="app" />
          <KindTag kind="주가" variant="web" />
          <Odometer value={n} style={{ fontSize: 21, fontWeight: '800', color: appColor.ink }} />
          <Text onPress={() => setN((x) => x + 1)}>+1</Text>
        </View>
        <Skeleton style={{ height: 60 }} />
        <AppSnackbar visible message="‘시장 한눈에 보기’ 위젯을 뺐어요" onUndo={() => {}} />
        <WebSnackbar visible message="메모를 휴지통으로 옮겼어요" onUndo={() => {}} />
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <Text onPress={() => setSheet(true)}>시트 열기</Text>
          <Text onPress={() => setDlg(true)}>확인 창</Text>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {(Object.keys(APP_ICONS) as (keyof typeof APP_ICONS)[]).map((k) => (
            <View key={k} style={{ width: 36, height: 36, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF' }}>
              <AppIcon name={k} size={24} />
            </View>
          ))}
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {(Object.keys(WEB_ICONS) as (keyof typeof WEB_ICONS)[]).map((k) => (
            <View key={k} style={{ width: 36, height: 36, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFFFFF' }}>
              <WebIcon name={k} size={24} />
            </View>
          ))}
        </View>
        <View style={{ height: 120 }} />
      </ScrollView>
      <Fab onPress={() => {}} style={{ position: 'absolute', right: 18, bottom: 16 }} />
      <Sheet open={sheet} onClose={() => setSheet(false)} title="위젯 추가" label="위젯 추가" width={480}>
        <View style={{ padding: 22, backgroundColor: '#FFFFFF', borderRadius: 20 }}>
          <Text>시트 내용</Text>
        </View>
      </Sheet>
      <ConfirmDialog variant="app" open={dlg} title="기본 구성으로 되돌릴까요?" body="지금 순서와 고른 위젯이 처음 구성(시장 · 업데이트 · 뉴스)으로 바뀌어요." confirmLabel="되돌리기" onCancel={() => setDlg(false)} onConfirm={() => setDlg(false)} />
    </View>
  );
}
