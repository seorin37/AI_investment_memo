import { useCallback, useEffect, useRef } from 'react';
import { Alert, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { env } from '@/config/env';
import { useAiOffAll, useAiOffNoticeSeen } from '@/hooks/queries';
import { useUI } from '@/store/ui';
import { useUsageView } from '@/ui/screens/my/useUsageView';

/**
 * 앱 'AI 사용량을 다 썼어요' 선택 (2026-11-24 서린 님 결정, 웹은 _layout 의 WebAiOffChoice).
 * 크레딧이 0이고 AI 연결 메모가 남아 있으면(끄기 대기): 충전 · 플랜 업그레이드 · AI 연결 모두 끄기.
 * 고르지 않고 닫으면 다음에 다시 묻는다 (그동안 매일 확인은 멈춤). 안드로이드 알림 창은 버튼이 3개까지라 '닫기'는 바깥 누르기.
 */
export function useAiOffChoice() {
  const router = useRouter();
  const usage = useUsageView();
  const off = useAiOffAll();
  const toast = useUI((s) => s.showToast);
  const count = usage.ai_count;
  return useCallback(() => {
    const buttons = [
      { text: '크레딧 충전', onPress: () => router.push('/studio-charge') },
      { text: '플랜 업그레이드', onPress: () => router.push('/my-plans') },
      {
        text: 'AI 연결 모두 끄기',
        style: 'destructive' as const,
        onPress: () =>
          off.mutate(undefined, {
            onSuccess: (r) => toast(`AI 연결 메모 ${r.turned_off}개를 껐어요. 메모는 그대로 남아 있어요`),
            onError: () => toast('AI 연결을 끄지 못했어요. 잠시 뒤 다시 해 주세요'),
          }),
      },
    ];
    Alert.alert(
      'AI 사용량을 다 썼어요',
      `크레딧을 충전하거나 플랜을 업그레이드하지 않으면 AI 연결 메모 ${count}개가 모두 꺼져요.\n메모는 그대로 남고, 꺼진 메모는 나중에 하나씩 다시 켤 수 있어요.`,
      Platform.OS === 'ios' ? [...buttons, { text: '닫기', style: 'cancel' as const }] : buttons,
      { cancelable: true },
    );
  }, [router, off, toast, count]);
}

/** 앱을 연 뒤 끄기 대기면 한 번 묻고, 갱신일에 자동으로 꺼진 메모가 있으면 한 번 알린다 (앱 탭 레이아웃에서 부름) */
export function useAiOffPrompt() {
  const usage = useUsageView();
  const ask = useAiOffChoice();
  const seen = useAiOffNoticeSeen();
  const asked = useRef(false);
  const told = useRef(false);
  const pending = !env.useMock && (usage.paused || usage.usage_pct >= 100) && usage.ai_count > 0;
  const autoOff = env.useMock ? 0 : usage.auto_off;
  useEffect(() => {
    if (!pending || asked.current) return;
    asked.current = true;
    ask();
  }, [pending, ask]);
  useEffect(() => {
    if (pending || autoOff <= 0 || told.current) return;
    told.current = true;
    Alert.alert(
      'AI 연결이 꺼졌어요',
      `지난 기간 AI 사용량을 다 써서 AI 연결 메모 ${autoOff}개가 꺼졌어요.\n메모는 그대로 남아 있어요. 다시 켤 메모를 골라 AI 연결을 켜 주세요.`,
      [{ text: '확인', onPress: () => seen.mutate() }],
      { cancelable: true, onDismiss: () => seen.mutate() },
    );
  }, [pending, autoOff, seen]);
}
