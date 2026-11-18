import React from 'react';
import { View } from 'react-native';
import { useRouter } from 'expo-router';
import { Button } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { colors } from '@/theme/tokens';

export default function NotFound() {
  const router = useRouter();
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, backgroundColor: colors.page }}>
      <T size={20} weight="bold">
        페이지를 찾을 수 없어요
      </T>
      <T size={14} color={colors.textSub}>
        주소가 바뀌었거나 삭제된 화면이에요.
      </T>
      <Button label="홈으로" onPress={() => router.replace('/')} />
    </View>
  );
}
