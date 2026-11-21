import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useStudioPlayer } from '@/store/studioPlayer';
import { mockLabNote, mockLabStocks, mockLabVars } from '@/ui/screens/studio/Studio.mock';
import { AppLab } from '@/ui/screens/studio/app/Lab';
import { labTitle } from '@/ui/screens/studio/labParts';

/** 앱 투자 실험실 (원본 studio.html pgLab). 실행은 크레딧 차감 없이 mock 결과를 만든 항목에 추가하고 결과 화면으로 */
export default function StudioLabScreen() {
  const router = useRouter();
  const code = useStudioPlayer((s) => s.labCode);
  const dirs = useStudioPlayer((s) => s.labDirs);
  const setLab = useStudioPlayer((s) => s.setLab);
  const addLab = useStudioPlayer((s) => s.addLab);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppLab
      vars={mockLabVars}
      stocks={mockLabStocks}
      code={code}
      dirs={dirs}
      note={mockLabNote}
      onBack={() => router.back()}
      onPick={(c) => setLab({ code: c })}
      onDir={(i, d) => setLab({ dirs: dirs.map((x, j) => (j === i ? d : x)) })}
      onReset={() => setLab({ dirs: mockLabVars.map(() => '유지') })}
      onRun={() => {
        const t = labTitle(code, dirs);
        addLab({ id: `m${Date.now()}`, kind: 'lab', title: t.title, sub: t.sub, meta: t.sub, left: '30일 뒤 삭제', lab: { code, dirs } });
        router.push({ pathname: '/studio-lab-result', params: { from: 'lab' } });
      }}
    />
  );
}
