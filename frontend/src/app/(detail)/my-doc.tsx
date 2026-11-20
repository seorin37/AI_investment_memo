import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { legalDocument } from '@/ui/screens/auth/Auth.mock';
import type { InfoDoc } from '@/ui/screens/my/My.types';
import { mockOss } from '@/ui/screens/my/My.mock';
import { AppDoc } from '@/ui/screens/my/app/Doc';

/** 앱 MY › 정보 › 약관·개인정보·오픈소스 (약관 전문은 ⑨-1 과 같은 AuthLegal) */
export default function MyDocScreen() {
  const router = useRouter();
  const { doc } = useLocalSearchParams<{ doc?: InfoDoc }>();
  if (Platform.OS === 'web') return <Redirect href="/" />;
  if (doc === 'oss' || !doc) return <AppDoc title="오픈소스 라이선스" oss={mockOss} onBack={() => router.back()} />;
  const d = legalDocument(doc);
  return <AppDoc title={d.title} html={d.html} onBack={() => router.back()} />;
}
