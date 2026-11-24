import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockReportKinds, mockStarLabels } from '@/ui/screens/my/My.mock';
import { AppFeedback } from '@/ui/screens/my/app/Feedback';

/** 앱 MY › 피드백 보내기 · 문의하기 (원본 my.html openFb). 보내기는 연결 안 됨 — 메일 앱·외부 전송 없음 */
export default function MyFeedbackScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <AppFeedback kinds={mockReportKinds} star_labels={mockStarLabels} onBack={() => router.back()} onSend={() => toast('아직 연결되지 않았어요')} />;
}
