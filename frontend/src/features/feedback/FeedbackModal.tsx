import React, { useState } from 'react';
import { Pressable, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Icon } from '@/components/icons/Icon';
import { Sheet, SheetHeader } from '@/components/ui/Modal';
import { Button, Hoverable, Segmented, TextArea, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useSendFeedback } from '@/hooks/queries';
import { useUI } from '@/store/ui';
import { colors } from '@/theme/tokens';

const BUG_TYPES = ['기능 작동 오류', '화면·표시 오류', '데이터·연결 오류', '속도·접속 문제', '기타'];

/** 9. 피드백 · 9.1 오류 신고 */
export function FeedbackModal({ onClose, initialTab = 'general' }: { onClose: () => void; initialTab?: 'general' | 'bug' }) {
  const [tab, setTab] = useState<'general' | 'bug'>(initialTab);
  const [rating, setRating] = useState(0);
  const [message, setMessage] = useState('');
  const [screen, setScreen] = useState('');
  const [cats, setCats] = useState<string[]>([]);
  const send = useSendFeedback();
  const toast = useUI((s) => s.showToast);

  const submit = () =>
    send.mutate(
      tab === 'general' ? { kind: 'general', rating, message } : { kind: 'bug', screen, categories: cats, message },
      {
        onSuccess: () => {
          toast('소중한 의견 고마워요!');
          onClose();
        },
      },
    );

  const canSend = message.trim().length > 0 && (tab === 'bug' || rating > 0);

  return (
    <Sheet visible onClose={onClose} width={520} padding={32} radius={28}>
      <SheetHeader
        title={tab === 'general' ? '피드백 보내기' : '오류 신고'}
        titleSize={24}
        description={tab === 'general'
          ? 'MEMO’S(메모스)를 사용하며 느낀 점을 알려주세요.\n소중한 의견을 모아 더 좋은 서비스를 만들겠습니다.'
          : '서비스 이용 중 발생한 문제를 알려주세요.\n남겨주신 내용을 확인하고 개선하겠습니다.'}
        onClose={onClose}
      />
      <Segmented
        tone="cool"
        items={[
          { key: 'general', label: '일반 피드백' },
          { key: 'bug', label: '오류 신고' },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === 'general' ? (
        <View style={{ alignItems: 'center', gap: 10, marginTop: 28 }}>
          <T size={15} weight="medium">
            얼마나 만족하셨나요?
          </T>
          <View style={{ flexDirection: 'row', gap: 18 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <Pressable key={n} onPress={() => setRating(n)} accessibilityLabel={`${n}점`} hitSlop={4}>
                <Svg width={30} height={30} viewBox="0 0 24 24">
                  <Path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.5 1.3 6.6L12 17.2l-5.9 3.3 1.3-6.6-4.9-4.5 6.6-.8z" fill={n <= rating ? '#FFC53D' : '#D5D8DE'} />
                </Svg>
              </Pressable>
            ))}
          </View>
          <T size={13} color={colors.textSub}>
            {rating ? ['', '아쉬워요', '그저 그래요', '괜찮아요', '좋아요', '최고예요'][rating] : '별점을 선택해 주세요'}
          </T>
        </View>
      ) : (
        <View style={{ gap: 10, marginTop: 24 }}>
          <T size={14} weight="semibold">
            문제가 발생한 화면·기능 (선택)
          </T>
          <TextField value={screen} onChangeText={setScreen} placeholder="예: 로그인, 투자 기록, 최신 업데이트" style={{ backgroundColor: '#F7F8FA', borderColor: '#EEF0F3' }} />
          <T size={11} color={colors.textSub}>
            문제가 발생한 위치를 알면 더 빠르게 확인할 수 있어요.
          </T>
          <T size={14} weight="semibold" style={{ marginTop: 8 }}>
            신고 유형 · 복수 선택 가능
          </T>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {BUG_TYPES.map((c) => {
              const on = cats.includes(c);
              return (
                <Hoverable
                  key={c}
                  accessibilityRole="button"
                  onPress={() => setCats((x) => (on ? x.filter((y) => y !== c) : [...x, c]))}
                  accessibilityState={{ selected: on }}
                  style={{ height: 34, paddingHorizontal: 18, borderRadius: 17, borderWidth: 1, borderColor: on ? colors.brand : colors.border, backgroundColor: on ? colors.brand : colors.surface, justifyContent: 'center', flexDirection: 'row', alignItems: 'center', gap: 8 }}
                  hoverStyle={{ opacity: 0.9 }}
                >
                  {on && <Icon name="check" size={12} color="#FFF" strokeWidth={2.5} />}
                  <T size={13} color={on ? '#FFF' : colors.textBody} lh={1.2}>
                    {c}
                  </T>
                </Hoverable>
              );
            })}
          </View>
        </View>
      )}

      <T size={14} weight="semibold" style={{ marginTop: 26, marginBottom: 10 }}>
        {tab === 'general' ? '피드백 내용' : '상세 내용'}
      </T>
      <TextArea
        value={message}
        onChangeText={(t) => setMessage(t.slice(0, 500))}
        placeholder={tab === 'general' ? '좋았던 점이나 개선이 필요한 점을\n자유롭게 작성해 주세요.' : '어떤 작업 중에 문제가 발생했나요?\n발생 상황과 기대했던 동작을 알려주세요.'}
        minHeight={156}
        style={{ backgroundColor: '#F8F9FB', borderWidth: 1, borderColor: '#E9ECF0', fontSize: 14 }}
      />
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 }}>
        <T size={11} color={colors.textSub}>
          개인정보는 입력하지 말아 주세요.
        </T>
        <T size={11} color={colors.textSub}>
          {message.length} / 500
        </T>
      </View>
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 22 }}>
        <Button label="취소" variant="secondary" size="lg" onPress={onClose} />
        <Button label="보내기" size="lg" onPress={submit} disabled={!canSend} loading={send.isPending} />
      </View>
    </Sheet>
  );
}
