import React, { useState } from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { MobileScreen, useMockNotice, useProfileAction } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { useLargeTitle } from '@/components/motion/Navigation';
import { MyStocks } from '@/features/stock/MyStocks';
import { mockMyStocksProps } from '@/features/stock/MyStocks.mock';
import { useBackClose } from '@/hooks/useBackClose';

/** 앱 내 종목 탭 (웹에는 이 화면이 없어 홈으로). mock 단계 */
export default function MyStocksTab() {
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <MyStocksScreen />;
}

function MyStocksScreen() {
  const router = useRouter();
  const profile = useProfileAction();
  const notice = useMockNotice();
  const lt = useLargeTitle();
  const [reorder, setReorder] = useState(false);
  useBackClose(() => {
    if (reorder) { setReorder(false); return true; }
    return false;
  });
  return (
    <MobileScreen
      bar={
        <TopBar
          left="title"
          title="내 종목"
          actions={reorder ? [{ kind: 'text', label: '완료', emphasis: true, onPress: () => setReorder(false) }] : [profile]}
          lineOpacity={lt.barLineOpacity}
        />
      }
    >
      <MyStocks
        {...mockMyStocksProps}
        reorder_mode={reorder}
        onOpenStock={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
        onAddStock={() => notice('종목 추가')}
        onLongPressStock={() => setReorder(true)}
        onReorder={() => notice('순서 저장')}
        onScroll={lt.onScroll}
      />
    </MobileScreen>
  );
}
