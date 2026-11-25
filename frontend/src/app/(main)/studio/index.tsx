import React from 'react';
import { Platform } from 'react-native';
import { Redirect } from 'expo-router';
import { StudioScreen } from '@/ui/screens/studio/app/StudioScreen';

/** 앱 스튜디오 탭 (웹 스튜디오 컴포넌트를 그대로 씀). 웹은 오른쪽 스튜디오 열을 쓰므로 홈으로 */
export default function StudioTab() {
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return <StudioScreen />;
}
