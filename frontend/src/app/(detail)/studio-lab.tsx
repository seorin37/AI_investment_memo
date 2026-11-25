import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockLabNote, mockLabVars } from '@/ui/screens/studio/Studio.mock';
import { AppLab } from '@/ui/screens/studio/app/Lab';
import { useLabStocks } from '@/ui/screens/studio/useLabRun';
import { startLab } from '@/ui/screens/studio/genRuns';
import { useLabVars } from '@/ui/screens/studio/useLabVars';

/** 앱 투자 실험실 (원본 studio.html pgLab). 실행하면 만드는 중 화면 → 결과 화면 */
export default function StudioLabScreen() {
  const router = useRouter();
  const code = useStudioPlayer((s) => s.labCode);
  const dirs = useStudioPlayer((s) => s.labDirs);
  const setLab = useStudioPlayer((s) => s.setLab);
  const stocks = useLabStocks();
  /* 변수 '지금 값': 실제 모드면 GET /market/macro (2026-11-21) */
  const vars = useLabVars();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  const stock = stocks.find((s) => s.stock_code === code) ?? stocks[0];
  return (
    <AppLab
      vars={vars}
      stocks={stocks}
      code={stock.stock_code}
      dirs={dirs}
      note={mockLabNote}
      onBack={() => router.back()}
      onPick={(c) => setLab({ code: c })}
      onDir={(i, d) => setLab({ dirs: dirs.map((x, j) => (j === i ? d : x)) })}
      onReset={() => setLab({ dirs: mockLabVars.map(() => '유지') })}
      onRun={() => router.push({ pathname: '/studio-gen', params: { id: startLab(stock, dirs) } })}
    />
  );
}
