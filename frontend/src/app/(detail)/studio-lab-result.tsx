import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockLabDisclaimer, mockLabStocks, mockLabVars } from '@/ui/screens/studio/Studio.mock';
import { AppLabResult } from '@/ui/screens/studio/app/LabResult';
import { labResultGroups } from '@/ui/screens/studio/labParts';
import { labStockFor, useLabStocks } from '@/ui/screens/studio/useLabRun';
import { useAddWatch } from '@/ui/screens/studio/useAddWatch';
import { useLabVars } from '@/ui/screens/studio/useLabVars';

/** 앱 실험 결과 (원본 studio.html pgLr). '조건 바꿔 다시 실험'은 그 조건을 실험실에 넣고 실험실로 */
export default function StudioLabResultScreen() {
  const router = useRouter();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curLab);
  const setLab = useStudioPlayer((s) => s.setLab);
  /* 변수 '지금 값': 실제 모드면 GET /market/macro (2026-11-21) */
  const vars = useLabVars();
  const stocks = useLabStocks();
  const item = made.find((m) => m.id === cur && m.kind === 'lab') ?? made.find((m) => m.kind === 'lab');
  const watch = useAddWatch('lab', item?.id ?? 'sample');
  if (Platform.OS === 'web') return <Redirect href="/" />;
  const lab = item?.lab ?? { code: mockLabStocks[0].stock_code, dirs: mockLabVars.map((v) => v.def) };
  const stock = labStockFor(stocks, lab);
  return (
    <AppLabResult
      stock={stock}
      vars={vars}
      groups={labResultGroups(lab)}
      disclaimer={mockLabDisclaimer}
      onBack={() => router.back()}
      onOpenMemo={() => router.push({ pathname: '/stocks/[code]', params: { code: stock.stock_code } })}
      isAdded={(title) => watch.isAdded(stock.stock_code, title)}
      onAdd={(title, why) => watch.add(stock, title, why)}
      onAgain={() => {
        setLab({ code: lab.code, dirs: lab.dirs });
        /* 실험실이 아래에 열려 있으면 그리로(원본 popPg), 없으면 실험실로 바꿔 열기 */
        router.dismissTo('/studio-lab');
      }}
    />
  );
}
