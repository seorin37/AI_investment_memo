import { useCallback, useEffect, useRef } from 'react';
import { BackHandler, Platform } from 'react-native';
import { useFocusEffect } from 'expo-router';

/**
 * 안드로이드 하드웨어 뒤로가기를 화면 안에서 먼저 처리 (고르기 해제 · 메뉴 닫기 · 편집 취소).
 * handler 가 true 를 돌려주면 여기서 끝, false 면 원래대로(화면 닫기 · 앱 나가기).
 * 이 화면이 보일 때(focus)만 듣는다 — 위에 다른 화면이 쌓이면 그 화면이 먼저 처리.
 */
export function useBackClose(handler: () => boolean) {
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useFocusEffect(
    useCallback(() => {
      if (Platform.OS !== 'android') return undefined;
      const sub = BackHandler.addEventListener('hardwareBackPress', () => ref.current());
      return () => sub.remove();
    }, []),
  );
}
