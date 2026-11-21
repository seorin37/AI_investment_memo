import React from 'react';
import { Platform } from 'react-native';
import { Redirect } from 'expo-router';
import { useCoach } from '@/store/coach';
import { mockFaq } from '@/ui/screens/my/My.mock';
import { WebHelp } from '@/ui/screens/my/web/Help';

/** 웹 도움말 = UI v2 (원본 overlays.tsx HelpPage). 앱은 MY › 도움말 */
export default function HelpScreen() {
  const replay = useCoach((s) => s.replay);
  if (Platform.OS !== 'web') return <Redirect href="/my-help" />;
  return <WebHelp faq={mockFaq} onReplayGuide={replay} />;
}
