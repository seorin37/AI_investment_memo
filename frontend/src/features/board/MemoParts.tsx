import React, { useState } from 'react';
import { Platform, Pressable, TextInput, View } from 'react-native';
import { Icon } from '@/components/icons/Icon';
import { AiToggle, Hoverable } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { colors, fonts, MEMO_COLORS, memoPalette } from '@/theme/tokens';
import type { MemoColor } from '@/types/models';

const webNoOutline = Platform.OS === 'web' ? ({ outlineStyle: 'none' } as object) : {};

/** 메모 색상 선택 (5색) */
export function ColorSwatches({ value, onChange, hint }: { value: MemoColor; onChange: (c: MemoColor) => void; hint: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
      <T size={12} color={colors.textWarm} style={{ width: 78 }}>
        메모 색상
      </T>
      {MEMO_COLORS.map((c) => {
        const on = c === value;
        return (
          <Pressable
            key={c}
            accessibilityRole="radio"
            accessibilityState={{ selected: on }}
            accessibilityLabel={`색상 ${c}`}
            onPress={() => onChange(c)}
            style={{
              width: 34,
              height: 34,
              borderRadius: 17,
              backgroundColor: memoPalette[c].swatch,
              borderWidth: on ? 1.5 : 0,
              borderColor: '#2E3138',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {on && <Icon name="check" size={16} color="#2E3138" strokeWidth={1.6} />}
          </Pressable>
        );
      })}
      <T size={12} color={colors.textWarm} style={{ marginLeft: 10 }}>
        {hint}
      </T>
    </View>
  );
}

/** 태그 행: 태그 칩 + [태그 추가/편집] → 인라인 입력 */
export function TagRow({ tags, onChange, buttonLabel = '태그 추가' }: { tags: string[]; onChange: (t: string[]) => void; buttonLabel?: string }) {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    const parts = (draft ?? '')
      .split(/[,\s]+/)
      .map((s) => s.replace(/^#/, '').trim())
      .filter(Boolean);
    if (parts.length) onChange(Array.from(new Set([...tags, ...parts])));
    setDraft(null);
  };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 34 }}>
      <View style={{ flex: 1, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
        {tags.length === 0 && draft === null && (
          <T size={12} color={colors.textWarm}>
            태그를 추가해 보세요
          </T>
        )}
        {tags.map((t) => (
          <Pressable key={t} onPress={() => onChange(tags.filter((x) => x !== t))} accessibilityLabel={`태그 ${t} 삭제`} style={{ flexDirection: 'row', alignItems: 'center', gap: 2 }}>
            <T size={12} weight="medium" color="#3C3842">
              #{t}
            </T>
            {draft !== null && <Icon name="x" size={10} color={colors.textMuted} />}
          </Pressable>
        ))}
        {draft !== null && (
          <TextInput
            autoFocus
            value={draft}
            onChangeText={setDraft}
            onSubmitEditing={commit}
            onBlur={commit}
            placeholder="태그 입력 후 Enter"
            placeholderTextColor={colors.placeholder}
            style={[{ minWidth: 120, height: 28, fontFamily: fonts.regular, fontSize: 13, color: colors.text, borderBottomWidth: 1, borderColor: colors.borderStrong }, webNoOutline]}
          />
        )}
      </View>
      <Hoverable
        onPress={() => (draft === null ? setDraft('') : commit())}
        style={{ height: 32, paddingHorizontal: 14, borderRadius: 10, backgroundColor: colors.surfaceWarm, justifyContent: 'center' }}
        hoverStyle={{ backgroundColor: '#ECE9E3' }}
      >
        <T size={14} weight="medium" lh={1.2}>
          {draft === null ? buttonLabel : '완료'}
        </T>
      </Hoverable>
    </View>
  );
}

/** AI 연결 카드 */
export function AiLinkCard({ value, onChange, title = 'AI 연결', desc }: { value: boolean; onChange: (v: boolean) => void; title?: string; desc: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surfaceWarm, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 16, gap: 12 }}>
      <View style={{ flex: 1, gap: 2 }}>
        <T size={15} weight="medium">
          {title}
        </T>
        <T size={12} color={colors.textWarm}>
          {desc}
        </T>
      </View>
      <AiToggle value={value} onChange={onChange} />
    </View>
  );
}

/** 메모 편집 영역 (색 배경 + 제목 + 본문) */
export function MemoEditArea({
  color,
  title,
  body,
  onTitle,
  onBody,
}: {
  color: MemoColor;
  title: string;
  body: string;
  onTitle: (t: string) => void;
  onBody: (t: string) => void;
}) {
  return (
    <View style={{ backgroundColor: memoPalette[color].swatch, borderRadius: 16, paddingHorizontal: 20, paddingVertical: 18, minHeight: 154, gap: 6 }}>
      <TextInput
        value={title}
        onChangeText={onTitle}
        placeholder="제목 (필수)"
        placeholderTextColor="#A39C8F"
        style={[{ fontFamily: fonts.semibold, fontSize: 17, color: colors.text, paddingVertical: 4 }, webNoOutline]}
        accessibilityLabel="메모 제목"
      />
      <TextInput
        value={body}
        onChangeText={onBody}
        multiline
        textAlignVertical="top"
        placeholder={'떠오르는 생각을 자유롭게 남겨보세요.\n기억하고 싶은 점이나 다음에 확인할 것을 적어도 좋아요.'}
        placeholderTextColor="#A39C8F"
        style={[{ fontFamily: fonts.regular, fontSize: 15, lineHeight: 26, color: colors.textBody, minHeight: 80 }, webNoOutline]}
        accessibilityLabel="메모 내용"
      />
    </View>
  );
}
