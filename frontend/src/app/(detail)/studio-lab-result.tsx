import React, { useState } from 'react';
import { Platform, View } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockLabDisclaimer, mockLabStocks, mockLabVars } from '@/ui/screens/studio/Studio.mock';
import { AppLabResult } from '@/ui/screens/studio/app/LabResult';
import { labResultGroups } from '@/ui/screens/studio/labParts';
import { labStockFor, useLabStocks } from '@/ui/screens/studio/useLabRun';
import { useLabMemo } from '@/ui/screens/studio/useLabMemo';
import { useLabVars } from '@/ui/screens/studio/useLabVars';
import { labWatchDraft, labWatchKey } from '@/ui/screens/studio/useLabWatch';
import { NewMemoSheet, type NewMemoTarget } from '@/ui/screens/memo/app/NewMemoSheet';

/** 앱 실험 결과 (원본 studio.html pgLr). '조건 바꿔 다시 실험'은 그 조건을 실험실에 넣고 실험실로 */
export default function StudioLabResultScreen() {
  const router = useRouter();
  const made = useStudioPlayer((s) => s.made);
  const cur = useStudioPlayer((s) => s.curLab);
  const setLab = useStudioPlayer((s) => s.setLab);
  /* 변수 '지금 값': 실제 모드면 GET /market/macro (2026-11-21) */
  const vars = useLabVars();
  const stocks = useLabStocks();
  const [memoTo, setMemoTo] = useState<NewMemoTarget | null>(null);
  const item = made.find((m) => m.id === cur && m.kind === 'lab') ?? made.find((m) => m.kind === 'lab');
  const memo = useLabMemo(item?.lab?.code ?? mockLabStocks[0].stock_code, true);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  const lab = item?.lab ?? { code: mockLabStocks[0].stock_code, dirs: mockLabVars.map((v) => v.def) };
  const stock = labStockFor(stocks, lab);
  return (
    <View style={{ flex: 1 }}>
    <AppLabResult
      stock={stock}
      vars={vars}
      groups={labResultGroups(lab)}
      disclaimer={mockLabDisclaimer}
      onBack={() => router.back()}
      isAdded={(i) => !!lab.added?.[labWatchKey(lab.code, i)]}
      onWatch={(check, why, i) => {
        const d = labWatchDraft({ check, why }, item?.title ?? '투자 실험');
        setMemoTo({ code: lab.code, name: stock.name, text: `${d.title}\n${d.body}`, ai: true, studio: { itemId: item?.server ? item.id : undefined, key: labWatchKey(lab.code, i) } });
      }}
      memo={memo}
      onMemo={(id) => (id ? router.push({ pathname: '/memo/[id]', params: { id } }) : setMemoTo({ code: lab.code, name: stock.name }))}
      onAgain={() => {
        setLab({ code: lab.code, dirs: lab.dirs });
        /* 실험실이 아래에 열려 있으면 그리로(원본 popPg), 없으면 실험실로 바꿔 열기 */
        router.dismissTo('/studio-lab');
      }}
    />
    <NewMemoSheet target={memoTo} onClose={() => setMemoTo(null)} />
    </View>
  );
}
