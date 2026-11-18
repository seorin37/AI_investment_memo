import React from 'react';
import { useRouter } from 'expo-router';
import { MobileScreen, useMockNotice } from '@/components/layout/MobileScreen';
import { TopBar } from '@/components/layout/TopBar';
import { WeeklyReport } from '@/features/studio/WeeklyReport';
import { mockWeeklyReportProps } from '@/features/studio/WeeklyReport.mock';

/** AI 주간보고서. mock 단계 (스튜디오는 백엔드 API 없음) */
export default function ReportScreen() {
  const router = useRouter();
  const notice = useMockNotice();
  return (
    <MobileScreen bar={<TopBar left="back" title="주간보고서" onBack={() => router.back()} />}>
      <WeeklyReport
        {...mockWeeklyReportProps}
        onAddWatch={() => notice('메모에 추가')}
        onOpenMemo={(code) => router.push({ pathname: '/stocks/[code]', params: { code } })}
      />
    </MobileScreen>
  );
}
