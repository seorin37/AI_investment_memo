import React from 'react';
import { Platform } from 'react-native';
import { Redirect } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockFaq } from '@/ui/screens/my/My.mock';
import { WebHelp } from '@/ui/screens/my/web/Help';

/** 웹 도움말 = UI v2 (원본 overlays.tsx HelpPage). 옛 화면은 features/help/LegacyHelpScreen (라우트에서만 뺌). 앱은 MY › 도움말 */
export default function HelpScreen() {
  const toast = useUI((s) => s.showToast);
  if (Platform.OS !== 'web') return <Redirect href="/my-help" />;
  return <WebHelp faq={mockFaq} onReplayGuide={() => toast('사용법 안내는 아직 준비 중이에요')} />;
}
