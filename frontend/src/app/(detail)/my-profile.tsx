import React from 'react';
import { Platform } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { useAuth } from '@/store/auth';
import { useMyProfile } from '@/ui/screens/my/useMyProfile';
import { useUI } from '@/store/ui';
import { AppProfile } from '@/ui/screens/my/app/Profile';

/**
 * 앱 내 프로필 = UI v2 (원본 app/my.html openProfile).
 * 로그아웃: mock 세션을 지우고 쌓인 화면을 비운 뒤 소개로 replace — 뒤로가기로 로그인 뒤 화면에 다시 못 들어감
 * (탭·상세 묶음은 로그인이 아니면 /intro 로 돌려보냄).
 */
export default function MyProfileScreen() {
  const router = useRouter();
  const toast = useUI((s) => s.showToast);
  /* 로그인한 사용자 프로필 (저장은 PATCH /me). mock 모드만 예시 프로필 */
  const { profile, save } = useMyProfile();
  const signOut = useAuth((s) => s.signOut);
  if (Platform.OS === 'web') return <Redirect href="/" />;
  return (
    <AppProfile
      profile={profile}
      onBack={() => router.back()}
      onChange={({ name, intro }) => {
        if (!name) {
          toast('이름은 비워 둘 수 없어요');
          return;
        }
        if (name !== profile.name || intro !== profile.intro) {
          save({ name, intro }).then(
            () => toast('프로필을 저장했어요'),
            (e: unknown) => toast(e instanceof Error && e.message ? e.message : '프로필을 저장하지 못했어요'),
          );
        }
      }}
      onPhoto={() => toast('아직 연결되지 않았어요 · 데이터는 그대로예요')}
      onPhotoDelete={() => toast('지울 사진이 없어요')}
      onLink={() => toast('계정을 연결했어요')}
      onLogout={() => {
        void signOut().finally(() => {
          if (router.canDismiss()) router.dismissAll();
          router.replace('/intro');
        });
      }}
      onWithdraw={() => router.push('/my-withdraw')}
    />
  );
}
