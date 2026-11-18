import React, { useEffect, useRef, useState } from 'react';
import { Linking, Platform, Pressable, ScrollView, TextInput, View, type TextInputInstance, type TextInputKeyPressEvent } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { api } from '@/api';
import { Icon, type IconName } from '@/components/icons/Icon';
import { CircleCheck, Hoverable, IconButton, Select } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useMyStocks, useUpdateJournal } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { longDateTime, uid } from '@/lib/format';
import { colors, fonts, shadow } from '@/theme/tokens';
import type { JournalBlock, JournalEntry } from '@/types/models';

const webNoOutline = Platform.OS === 'web' ? ({ outlineStyle: 'none' } as object) : {};

/**
 * 투자 기록 편집기 — 애플 메모처럼 단순하게.
 * 글쓰기 도구는 5개만(가가 · 체크리스트 · 표 · 첨부 · 마크업), 편집 영역 아래 떠 있는 바(B안).
 * 입력이 멈추면 0.7초 뒤 자동 저장합니다.
 */
export function JournalEditor({ entry, onDelete }: { entry: JournalEntry; onDelete: () => void }) {
  const [title, setTitle] = useState(entry.title);
  const [blocks, setBlocks] = useState<JournalBlock[]>(entry.blocks.length ? entry.blocks : [{ id: uid('b'), type: 'paragraph', text: '' }]);
  const [stockCode, setStockCode] = useState<string | null>(entry.stock_code);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const refs = useRef(new Map<string, TextInputInstance | null>());
  const titleRef = useRef<TextInputInstance>(null);
  const [edits, setEdits] = useState(0); // 사용자 편집 횟수 (0 = 아직 수정 없음 → 저장 안 함)
  const [startEmpty] = useState(!entry.title);
  const update = useUpdateJournal();
  const { data: stocks = [] } = useMyStocks();
  const { isMobile } = useBreakpoint();

  // 새 기록이면 제목에 바로 커서
  useEffect(() => {
    if (!startEmpty) return;
    const t = setTimeout(() => titleRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [startEmpty]);

  // 자동 저장 (마지막 입력 0.7초 뒤)
  useEffect(() => {
    if (edits === 0) return;
    const t = setTimeout(() => {
      update.mutate({ id: entry.id, patch: { title, blocks, stock_code: stockCode } }, { onSuccess: () => setSaveState('saved') });
    }, 700);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edits]);

  useEffect(() => {
    if (focusId) refs.current.get(focusId)?.focus();
  }, [focusId, blocks.length]);

  const touch = () => {
    setEdits((n) => n + 1);
    setSaveState('saving');
  };
  const mutate = (fn: (b: JournalBlock[]) => JournalBlock[]) => {
    touch();
    setBlocks((b) => fn(b));
  };
  const patchBlock = (id: string, patch: Partial<JournalBlock>) => mutate((bs) => bs.map((b) => (b.id === id ? ({ ...b, ...patch } as JournalBlock) : b)));
  const insertAfter = (id: string | null, block: JournalBlock) =>
    mutate((bs) => {
      const i = id ? bs.findIndex((b) => b.id === id) : bs.length - 1;
      const next = [...bs];
      next.splice(i + 1, 0, block);
      return next;
    });
  const removeBlock = (id: string) => {
    const i = blocks.findIndex((b) => b.id === id);
    const prev = blocks[i - 1] ?? blocks[i + 1];
    if (prev) setFocusId(prev.id);
    mutate((bs) => {
      const next = bs.filter((b) => b.id !== id);
      return next.length ? next : [{ id: uid('b'), type: 'paragraph', text: '' }];
    });
  };

  const focused = blocks.find((b) => b.id === focusId);
  const current = focused ?? blocks[blocks.length - 1];

  // ─── 도구 막대
  const tools: { icon: IconName | 'text'; label: string; run: () => void; active?: boolean }[] = [
    {
      icon: 'text',
      label: '글자 스타일 (본문/소제목)',
      active: focused?.type === 'heading',
      run: () => {
        if (!current) return;
        if (current.type === 'paragraph') patchBlock(current.id, { type: 'heading' } as Partial<JournalBlock>);
        else if (current.type === 'heading' || current.type === 'checklist') {
          const text = current.text;
          mutate((bs) => bs.map((b) => (b.id === current.id ? { id: b.id, type: 'paragraph', text } : b)));
        }
      },
    },
    {
      icon: 'listChecks',
      label: '체크리스트',
      active: focused?.type === 'checklist',
      run: () => {
        if (current && (current.type === 'paragraph' || current.type === 'heading')) {
          const text = current.text;
          mutate((bs) => bs.map((b) => (b.id === current.id ? { id: b.id, type: 'checklist', text, checked: false } : b)));
        } else {
          const nb: JournalBlock = { id: uid('b'), type: 'checklist', text: '', checked: false };
          insertAfter(current?.id ?? null, nb);
          setFocusId(nb.id);
        }
      },
    },
    {
      icon: 'table',
      label: '표',
      run: () => {
        insertAfter(current?.id ?? null, { id: uid('b'), type: 'table', rows: [['', ''], ['', '']] });
      },
    },
    {
      icon: 'paperclip',
      label: '첨부',
      run: async () => {
        const res = await DocumentPicker.getDocumentAsync({ multiple: false, copyToCacheDirectory: true });
        if (res.canceled || !res.assets?.[0]) return;
        const a = res.assets[0];
        const up = await api.uploadFile({ uri: a.uri, name: a.name, mimeType: a.mimeType, file: (a as { file?: Blob }).file });
        insertAfter(current?.id ?? null, { id: uid('b'), type: 'attachment', name: up.name, url: up.url });
      },
    },
    {
      icon: 'markup',
      label: '마크업 (형광펜)',
      active: !!(focused && 'highlight' in focused && focused.highlight),
      run: () => {
        if (current && (current.type === 'paragraph' || current.type === 'heading')) patchBlock(current.id, { highlight: !current.highlight } as Partial<JournalBlock>);
      },
    },
  ];

  return (
    <View style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ paddingHorizontal: isMobile ? 20 : 72, paddingTop: isMobile ? 16 : 32, paddingBottom: 140 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 18 }}>
          <T size={12} color={colors.textMuted} tabular>
            {longDateTime(entry.created_at)}
          </T>
          {saveState !== 'idle' && (
            <T size={11} color={colors.textMuted}>
              · {saveState === 'saving' ? '저장 중…' : '저장됨'}
            </T>
          )}
        </View>
        <View style={{ flexDirection: isMobile ? 'column-reverse' : 'row', alignItems: isMobile ? 'stretch' : 'center', gap: 8 }}>
          <TextInput
            ref={titleRef}
            value={title}
            onChangeText={(t) => {
              touch();
              setTitle(t);
            }}
            placeholder="제목"
            placeholderTextColor={colors.placeholder}
            style={[{ flex: isMobile ? undefined : 1, minWidth: 0, fontFamily: fonts.bold, fontSize: isMobile ? 22 : 26, color: colors.text, paddingVertical: 6 }, webNoOutline]}
            onSubmitEditing={() => setFocusId(blocks[0]?.id ?? null)}
            accessibilityLabel="기록 제목"
          />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, justifyContent: 'flex-end', zIndex: 5 }}>
            <View style={{ width: 150 }}>
              <Select
                value={stockCode ?? '__none'}
                options={[{ key: '__none', label: '종목 없음' }, ...stocks.map((s) => ({ key: s.code, label: s.name }))]}
                onChange={(k) => {
                  touch();
                  setStockCode(k === '__none' ? null : k);
                }}
              />
            </View>
            <IconButton name="trash" label="기록 삭제" onPress={onDelete} color={colors.textMuted} size={18} />
          </View>
        </View>

        <View style={{ gap: 4, marginTop: 6 }}>
          {blocks.map((b) => (
            <BlockView
              key={b.id}
              block={b}
              setRef={(r) => refs.current.set(b.id, r)}
              onFocus={() => setFocusId(b.id)}
              onChange={(patch) => patchBlock(b.id, patch)}
              onEnter={() => {
                const nb: JournalBlock = b.type === 'checklist' ? { id: uid('b'), type: 'checklist', text: '', checked: false } : { id: uid('b'), type: 'paragraph', text: '' };
                if (b.type === 'checklist' && b.text === '') {
                  // 빈 체크 항목에서 Enter → 일반 문단으로 빠져나오기
                  mutate((bs) => bs.map((x) => (x.id === b.id ? { id: x.id, type: 'paragraph', text: '' } : x)));
                  return;
                }
                insertAfter(b.id, nb);
                setFocusId(nb.id);
              }}
              onBackspaceEmpty={() => blocks.length > 1 && removeBlock(b.id)}
              onRemove={() => removeBlock(b.id)}
            />
          ))}
          <Pressable
            onPress={() => {
              const last = blocks[blocks.length - 1];
              if (last && last.type === 'paragraph' && last.text === '') return setFocusId(last.id);
              const nb: JournalBlock = { id: uid('b'), type: 'paragraph', text: '' };
              insertAfter(last?.id ?? null, nb);
              setFocusId(nb.id);
            }}
            style={{ height: 240 }}
            accessibilityLabel="이어서 쓰기"
          />
        </View>
      </ScrollView>

      {/* 떠 있는 글쓰기 도구 (B안) */}
      <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, right: 0, bottom: 24, alignItems: 'center' }}>
        <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 22, paddingHorizontal: 10, height: 44, alignItems: 'center', gap: 4, borderWidth: 1, borderColor: '#EFEFF1', ...shadow.pop }}>
          {tools.map((t) => (
            <Hoverable
              key={t.label}
              accessibilityRole="button"
              accessibilityLabel={t.label}
              onPress={() => void t.run()}
              style={[{ width: 36, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' }, t.active && { backgroundColor: '#F1ECFB' }]}
              hoverStyle={{ backgroundColor: '#F4F4F6' }}
            >
              {t.icon === 'text' ? (
                <T size={15} weight="medium" lh={1}>
                  가<T size={10} weight="medium">가</T>
                </T>
              ) : (
                <Icon name={t.icon} size={18} color={colors.text} strokeWidth={1.6} />
              )}
            </Hoverable>
          ))}
        </View>
      </View>
    </View>
  );
}

function BlockView({
  block,
  setRef,
  onFocus,
  onChange,
  onEnter,
  onBackspaceEmpty,
  onRemove,
}: {
  block: JournalBlock;
  setRef: (r: TextInputInstance | null) => void;
  onFocus: () => void;
  onChange: (patch: Partial<JournalBlock>) => void;
  onEnter: () => void;
  onBackspaceEmpty: () => void;
  onRemove: () => void;
}) {
  const onKey = (e: TextInputKeyPressEvent, empty: boolean) => {
    if (e.nativeEvent.key === 'Backspace' && empty) onBackspaceEmpty();
  };

  if (block.type === 'paragraph' || block.type === 'heading') {
    const heading = block.type === 'heading';
    return (
      <TextInput
        ref={setRef}
        value={block.text}
        onChangeText={(text) => onChange({ text })}
        onFocus={onFocus}
        onKeyPress={(e) => onKey(e, block.text === '')}
        multiline
        scrollEnabled={false}
        // 웹: textarea 기본 2줄 → 1줄로 시작해 내용만큼 자동으로 늘어나게
        {...(Platform.OS === 'web' ? { numberOfLines: 1 } : {})}
        placeholder={heading ? '소제목' : '내용을 입력하세요'}
        placeholderTextColor="#D0D4DA"
        style={[
          {
            fontFamily: heading ? fonts.bold : fonts.regular,
            fontSize: heading ? 18 : 15,
            lineHeight: heading ? 28 : 24,
            color: colors.text,
            paddingVertical: heading ? 8 : 4,
            marginTop: heading ? 8 : 0,
          },
          Platform.OS === 'web' && ({ fieldSizing: 'content', resize: 'none' } as object),
          block.highlight && { backgroundColor: '#FFF4C6', borderRadius: 4, paddingHorizontal: 4 },
          webNoOutline,
        ]}
      />
    );
  }
  if (block.type === 'checklist') {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 32 }}>
        <CircleCheck checked={block.checked} onPress={() => onChange({ checked: !block.checked })} tone="gray" />
        <TextInput
          ref={setRef}
          value={block.text}
          onChangeText={(text) => onChange({ text })}
          onFocus={onFocus}
          onKeyPress={(e) => onKey(e, block.text === '')}
          onSubmitEditing={onEnter}
          blurOnSubmit={false}
          returnKeyType="next"
          placeholder="할 일"
          placeholderTextColor="#D0D4DA"
          style={[
            { flex: 1, minWidth: 0, fontFamily: fonts.regular, fontSize: 15, color: block.checked ? colors.textMuted : colors.text, textDecorationLine: block.checked ? 'line-through' : 'none', paddingVertical: 4 },
            webNoOutline,
          ]}
        />
      </View>
    );
  }
  if (block.type === 'table') {
    const rows = block.rows;
    const setCell = (r: number, c: number, v: string) => onChange({ rows: rows.map((row, ri) => (ri === r ? row.map((cell, ci) => (ci === c ? v : cell)) : row)) } as Partial<JournalBlock>);
    return (
      <View style={{ marginVertical: 8, gap: 6 }}>
        <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 8, overflow: 'hidden' }}>
          {rows.map((row, ri) => (
            <View key={ri} style={{ flexDirection: 'row', borderTopWidth: ri ? 1 : 0, borderColor: colors.border, backgroundColor: ri === 0 ? '#FAFAFB' : '#FFF' }}>
              {row.map((cell, ci) => (
                <TextInput
                  key={ci}
                  value={cell}
                  onFocus={onFocus}
                  onChangeText={(v) => setCell(ri, ci, v)}
                  style={[{ flex: 1, minHeight: 36, paddingHorizontal: 10, fontFamily: ri === 0 ? fonts.semibold : fonts.regular, fontSize: 14, color: colors.text, borderLeftWidth: ci ? 1 : 0, borderColor: colors.border }, webNoOutline]}
                />
              ))}
            </View>
          ))}
        </View>
        <View style={{ flexDirection: 'row', gap: 12 }}>
          <SmallLink label="+ 행" onPress={() => onChange({ rows: [...rows, rows[0].map(() => '')] } as Partial<JournalBlock>)} />
          <SmallLink label="+ 열" onPress={() => onChange({ rows: rows.map((r) => [...r, '']) } as Partial<JournalBlock>)} />
          <SmallLink label="표 삭제" onPress={onRemove} danger />
        </View>
      </View>
    );
  }
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', backgroundColor: '#F5F6F8', borderRadius: 10, paddingHorizontal: 12, height: 36, marginVertical: 4 }}>
      <Icon name="paperclip" size={14} color={colors.textSub} />
      <Pressable onPress={() => void Linking.openURL(block.url)}>
        <T size={13} weight="medium">
          {block.name}
        </T>
      </Pressable>
      <IconButton name="x" label="첨부 삭제" size={12} box={20} onPress={onRemove} />
    </View>
  );
}

function SmallLink({ label, onPress, danger }: { label: string; onPress: () => void; danger?: boolean }) {
  return (
    <Pressable onPress={onPress} hitSlop={6}>
      <T size={12} color={danger ? colors.danger : colors.textSub}>
        {label}
      </T>
    </Pressable>
  );
}
