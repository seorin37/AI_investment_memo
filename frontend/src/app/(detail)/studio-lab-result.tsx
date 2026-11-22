import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockLabDisclaimer, mockLabStocks, mockLabVars } from '@/ui/screens/studio/Studio.mock';
import { AppLabResult } from '@/ui/screens/studio/app/LabResult';
import { labResultGroups } from '@/ui/screens/studio/labParts';
import { labStockFor, useLabStocks } from '@/ui/screens/studio/useLabRun';
import { useLabVars } from '@/ui/screens/studio/useLabVars';

/** 앱 실험 결과 (원본 studio.html pgLr). '조건 바꿔 다시 실험'은 그 조건을 실험실에 넣고 실험실로 */
export default function StudioLabResultScreen() {
  const router = useRouter();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curLab);
  const setLab = useStudioPlayer((s) => s.setLab);
  const { from } = useLocalSearchParams<{ from?: string }>();
  /* 변수 '지금 값': 실제 모드면 GET /market/macro (2026-11-21) */
  const vars = useLabVars();
  const stocks = useLabStocks();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  const item = made.find((m) => m.id === cur && m.kind === 'lab') ?? made.find((m) => m.kind === 'lab');
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
      onAgain={() => {
        setLab({ code: lab.code, dirs: lab.dirs });
        /* 실험실에서 왔으면 뒤로(원본 popPg), 만든 항목에서 왔으면 실험실로 바꿔 열기 */
        if (from === 'lab') router.back();
        else router.replace('/studio-lab');
      }}
    />
  );
}
