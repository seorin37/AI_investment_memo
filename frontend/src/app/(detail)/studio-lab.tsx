import React from 'react';
import { Platform } from 'react-native';
import { Redirect } from 'expo-router';

/** 스튜디오 화면은 모두 스튜디오 탭 안에 있음 (옛 주소). 웹은 전과 같이 홈으로 */
export default function OldStudioRoute() {
  return <Redirect href={Platform.OS === 'web' ? '/' : '/studio'} />;
}
