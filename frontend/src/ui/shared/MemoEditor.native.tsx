import React, { useImperativeHandle, useRef, useState } from 'react';
import { StyleSheet, View, type TextInputInstance } from 'react-native';
import { Text, TextInput } from '@/components/ui/AppText';
import { appColor, ft, webColor } from '@/ui/theme';
import { ON_DOM } from './onDom';
import type { MemoEditorProps } from './MemoEditor.types';

/**
 * 앱 한 칸 메모 편집 (원본 memo.html .ed: 15.5px 줄 1.8 #2E2E38 · 첫 줄 21px 800 줄 1.4 #16171A · 커서 #6A42AB).
 * 줄마다 글자 묶음을 넣어 첫 줄만 제목 크기로 (아이폰 메모 방식). 저장은 부모가 splitMemo.
 * 보기 상태는 같은 모양의 글자, 편집할 때만 입력 칸 (커서는 글 끝에서 시작).
 */
export function MemoEditor({ value, onChangeText, editable, autoFocus, variant, onFocus, focusRef, accessibilityLabel }: MemoEditorProps) {
  const ref = useRef<TextInputInstance>(null);
  const [sel, setSel] = useState<{ start: number; end: number } | undefined>(() => ({ start: value.length, end: value.length }));
  useImperativeHandle(focusRef, () => ({
    focus: () => ref.current?.focus(),
    blur: () => ref.current?.blur(),
  }));
  const nl = value.indexOf('\n');
  const first = nl < 0 ? value : value.slice(0, nl);
  const rest = nl < 0 ? '' : value.slice(nl);
  const s = variant === 'app' ? app : web;
  const lines = (
    <>
      <Text style={s.title}>{first}</Text>
      {rest ? <Text style={s.body}>{rest}</Text> : null}
    </>
  );
  if (!editable)
    return (
      <Text style={s.box} accessibilityLabel={accessibilityLabel}>
        {lines}
      </Text>
    );
  const input = (
    <TextInput
      ref={ref}
      multiline
      {...(ON_DOM ? { value } : null)}
      autoFocus={autoFocus ?? true}
      onFocus={onFocus}
      onChangeText={onChangeText}
      selection={sel}
      onSelectionChange={() => sel && setSel(undefined)}
      scrollEnabled={false}
      textAlignVertical="top"
      selectionColor={variant === 'app' ? appColor.deepPurple : webColor.ink}
      cursorColor={variant === 'app' ? appColor.deepPurple : webColor.ink}
      accessibilityLabel={accessibilityLabel ?? '메모 (첫 줄은 제목)'}
      style={[s.box, ON_DOM && dom.input]}
    >
      {/* 브라우저 미리보기의 textarea 는 글자 묶음(children)을 못 받아 value 로 */}
      {ON_DOM ? null : lines}
    </TextInput>
  );
  if (!ON_DOM) return input;
  /* 미리보기: 제목 크기가 보이게 글자를 뒤에 그리고 입력 칸 글자는 투명 */
  return (
    <View>
      <Text style={s.box}>{lines}</Text>
      {input}
    </View>
  );
}

const dom = StyleSheet.create({
  input: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, minHeight: 120, color: 'transparent', caretColor: '#15171A', outlineStyle: 'none' } as object,
});
const app = StyleSheet.create({
  box: { ...ft(16, 1.8), color: '#2E2E38', padding: 0, margin: 0, minHeight: 120 },
  title: { ...ft(21, 1.4), fontWeight: '800', color: appColor.ink },
  body: { ...ft(16, 1.8), color: '#2E2E38' },
});
const web = StyleSheet.create({
  box: { fontSize: 16, lineHeight: 25.6, color: '#333D4B', padding: 0, margin: 0 },
  title: { fontSize: 21, lineHeight: 25, fontWeight: '700', color: webColor.ink },
  body: { fontSize: 16, lineHeight: 25.6, color: '#333D4B' },
});
