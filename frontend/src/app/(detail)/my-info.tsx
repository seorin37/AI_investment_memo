import React from 'react';
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { Redirect, useRouter } from 'expo-router';
import { useUI } from '@/store/ui';
import { mockDataSources } from '@/ui/screens/my/My.mock';
import { AppInfo } from '@/ui/screens/my/app/Info';

/** 앱 MY › 정보 (원본 my.html openInfo). 버전은 app.json 의 version (expo-constants) */
export default function MyInfoScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppInfo
      version={Constants.expoConfig?.version ?? ''}
      sources={mockDataSources}
      onBack={() => router.back()}
      onDoc={(doc) => router.push({ pathname: '/my-doc', params: { doc } })}
      onFeedback={() => toast('피드백 화면은 다음 묶음에서 열려요')}
    />
  );
}
