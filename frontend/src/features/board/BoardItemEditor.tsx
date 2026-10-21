import React, { useMemo, useState } from 'react';
import { Linking, Platform, Pressable, TextInput, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { api } from '@/api';
import { Icon } from '@/components/icons/Icon';
import { Sheet, SheetHeader } from '@/components/ui/Modal';
import { Button, CircleCheck, Hoverable, IconButton, InfoNote, Loading, ProgressRing, Segmented, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useBoard, useCreateBoardItem, useDeleteBoardItem, useMyStocks, useSettings, useUpdateBoardItem } from '@/hooks/queries';
import { uid } from '@/lib/format';
import { useUI } from '@/store/ui';
import { colors, fonts } from '@/theme/tokens';
import type { BoardItem, BoardItemKind, ChecklistItem, MemoColor, ReferenceLink, ReferenceType } from '@/types/models';
import { refTypeLabel } from './BoardCards';
import { AiLinkCard, ColorSwatches, MemoEditArea, TagRow } from './MemoParts';

const webNoOutline = Platform.OS === 'web' ? ({ outlineStyle: 'none' } as object) : {};
const KIND_TITLE: Record<BoardItemKind, string> = { memo: '메모', checklist: '체크리스트', reference: '참고자료' };
const REF_TYPES: { key: ReferenceType; label: string }[] = [
  { key: 'ir', label: '기업 IR' },
  { key: 'news', label: '뉴스' },
  { key: 'report', label: '리포트' },
  { key: 'disclosure', label: '공시' },
  { key: 'etc', label: '기타' },
];

/**
 * 6.1~6.3 새 메모 · 새 체크리스트 · 새 참고자료 (보드 항목 생성/수정)
 * 체크리스트와 참고자료는 AI 연결 기능이 없습니다(팀 결정).
 */
export function BoardItemEditor({ onClose, stockCode, initialKind = 'memo', itemId }: { onClose: () => void; stockCode: string; initialKind?: BoardItemKind; itemId?: string }) {
  const { data: board, isLoading } = useBoard(stockCode);
  const { data: settings, isLoading: settingsLoading } = useSettings();
  const editing = useMemo(() => board?.find((b) => b.id === itemId), [board, itemId]);
  // 수정 대상/설정이 준비된 뒤에 편집기를 그려 초기값을 한 번에 채움
  if ((itemId && isLoading) || settingsLoading)
    return (
      <Sheet visible onClose={onClose} width={640}>
        <Loading height={300} />
      </Sheet>
    );
  return (
    <EditorBody
      key={editing?.id ?? 'new'}
      onClose={onClose}
      stockCode={stockCode}
      initialKind={initialKind}
      editing={editing}
      defaultAi={settings?.ai.default_link_new_memo ?? false}
    />
  );
}

function EditorBody({
  onClose,
  stockCode,
  initialKind,
  editing,
  defaultAi,
}: {
  onClose: () => void;
  stockCode: string;
  initialKind: BoardItemKind;
  editing: BoardItem | undefined;
  defaultAi: boolean;
}) {
  const { data: stocks } = useMyStocks();
  const [kind, setKind] = useState<BoardItemKind>(editing?.kind ?? initialKind);
  const create = useCreateBoardItem(stockCode);
  const update = useUpdateBoardItem(stockCode);
  const remove = useDeleteBoardItem(stockCode);
  const toast = useUI((s) => s.showToast);
  const stockName = stocks?.find((s) => s.code === stockCode)?.name ?? stockCode;
  const memo = editing?.kind === 'memo' ? editing : null;
  const checklist = editing?.kind === 'checklist' ? editing : null;
  const reference = editing?.kind === 'reference' ? editing : null;

  // 메모
  const [title, setTitle] = useState(memo?.title ?? '');
  const [body, setBody] = useState(memo?.body ?? '');
  const [tags, setTags] = useState<string[]>(memo?.tags ?? []);
  const [color, setColor] = useState<MemoColor>(memo?.color ?? 'yellow');
  const [ai, setAi] = useState(memo?.ai_linked ?? defaultAi);
  // 체크리스트
  const [clTitle, setClTitle] = useState(checklist?.title ?? '체크리스트');
  const [items, setItems] = useState<ChecklistItem[]>(checklist?.items ?? []);
  const [newItem, setNewItem] = useState('');
  // 참고자료
  const [refTitle, setRefTitle] = useState(reference?.title ?? '참고 자료');
  const [links, setLinks] = useState<ReferenceLink[]>(reference?.links ?? []);
  const [url, setUrl] = useState('');
  const [refType, setRefType] = useState<ReferenceType>('ir');
  const [error, setError] = useState<string | null>(null);

  const busy = create.isPending || update.isPending;

  const addLink = () => {
    const v = url.trim();
    if (!v) return;
    const href = /^https?:\/\//.test(v) ? v : `https://${v}`;
    let name = href;
    try {
      const u = new URL(href);
      name = `${u.hostname.replace(/^www\./, '')}${u.pathname.length > 1 ? u.pathname.slice(0, 24) : ''}`;
    } catch {
      /* 그대로 */
    }
    setLinks((l) => [...l, { id: uid('rl'), title: name, url: href, ref_type: refType, source: 'link' }]);
    setUrl('');
  };

  const attachFile = async () => {
    const res = await DocumentPicker.getDocumentAsync({ multiple: false, copyToCacheDirectory: true });
    if (res.canceled || !res.assets?.[0]) return;
    const a = res.assets[0];
    try {
      const up = await api.uploadFile({ uri: a.uri, name: a.name, mimeType: a.mimeType, file: (a as { file?: Blob }).file });
      setLinks((l) => [...l, { id: uid('rl'), title: up.name, url: up.url, ref_type: refType, source: 'file' }]);
    } catch {
      setError('파일을 올리지 못했어요.');
    }
  };

  const save = () => {
    setError(null);
    const done = () => {
      toast(editing ? '저장했어요' : `${KIND_TITLE[kind]}를 보드에 추가했어요`);
      onClose();
    };
    if (kind === 'memo') {
      if (!title.trim()) return setError('제목을 입력해 주세요.');
      if (editing) update.mutate({ id: editing.id, patch: { title: title.trim(), body, tags, color } }, { onSuccess: done });
      else create.mutate({ kind: 'memo', input: { title: title.trim(), body, tags, color, ai_linked: ai } }, { onSuccess: done });
    } else if (kind === 'checklist') {
      const all = newItem.trim() ? [...items, { id: uid('ci'), text: newItem.trim(), done: false }] : items;
      if (editing) update.mutate({ id: editing.id, patch: { title: clTitle, items: all } }, { onSuccess: done });
      else create.mutate({ kind: 'checklist', input: { title: clTitle, items: all } }, { onSuccess: done });
    } else {
      if (editing) update.mutate({ id: editing.id, patch: { title: refTitle, links } }, { onSuccess: done });
      else create.mutate({ kind: 'reference', input: { title: refTitle, links } }, { onSuccess: done });
    }
  };

  const doneCount = items.filter((i) => i.done).length;
  const footerHint = { memo: 'AI 연결은 선택사항이에요', checklist: '저장 후에도 언제든 고칠 수 있어요', reference: '링크는 새 탭에서 열려요' }[kind];

  return (
    <Sheet visible onClose={onClose} width={640} padding={24}>
      <SheetHeader eyebrow={`${stockName} · 나의 보드`} title={`${editing ? '' : '새 '}${KIND_TITLE[kind]}${editing ? ' 수정' : ''}`} onClose={onClose} />
      {!editing && (
        <View style={{ marginBottom: 24 }}>
          <Segmented
            items={[
              { key: 'memo', label: '메모' },
              { key: 'checklist', label: '체크리스트' },
              { key: 'reference', label: '참고자료' },
            ]}
            value={kind}
            onChange={setKind}
          />
        </View>
      )}

      {kind === 'memo' && (
        <View style={{ gap: 14 }}>
          <SectionTitle title="내 메모" hint="제목은 필수예요" />
          <MemoEditArea color={color} title={title} body={body} onTitle={setTitle} onBody={setBody} />
          <TagRow tags={tags} onChange={setTags} />
          <ColorSwatches value={color} onChange={setColor} hint="보기·수정 칸에 같은 색상" />
          <View style={{ height: 28 }} />
          {!editing && <AiLinkCard value={ai} onChange={setAi} desc="메모는 자유롭게, 지켜볼 내용만 AI로." />}
        </View>
      )}

      {kind === 'checklist' && (
        <View style={{ gap: 14 }}>
          <SectionTitle title="체크리스트 제목" hint="보드 카드 제목으로 보여요" />
          <TextField value={clTitle} onChangeText={setClTitle} style={{ height: 48, borderRadius: 12 }} inputStyle={{ fontFamily: fonts.semibold }} />
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
            <T size={16} weight="bold">
              확인할 항목
            </T>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <T size={12} color={colors.textWarm}>
                {doneCount} / {items.length} 완료
              </T>
              <ProgressRing done={doneCount} total={items.length} size={30} />
            </View>
          </View>
          <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 6 }}>
            {items.map((it) => (
              <View key={it.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, height: 44, borderBottomWidth: 1, borderColor: colors.borderSoft }}>
                <CircleCheck checked={it.done} onPress={() => setItems((l) => l.map((x) => (x.id === it.id ? { ...x, done: !x.done } : x)))} />
                <TextInput
                  value={it.text}
                  onChangeText={(t) => setItems((l) => l.map((x) => (x.id === it.id ? { ...x, text: t } : x)))}
                  style={[{ flex: 1, minWidth: 0, fontFamily: fonts.regular, fontSize: 15, color: it.done ? colors.textMuted : colors.textBody, textDecorationLine: it.done ? 'line-through' : 'none' }, webNoOutline]}
                />
                <IconButton name="x" label="항목 삭제" size={16} onPress={() => setItems((l) => l.filter((x) => x.id !== it.id))} color={colors.textMuted} />
              </View>
            ))}
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, height: 46 }}>
              <View style={{ width: 20, height: 20, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', borderColor: '#C9CDD4', alignItems: 'center', justifyContent: 'center' }}>
                <Icon name="plus" size={10} color={colors.textMuted} />
              </View>
              <TextInput
                value={newItem}
                onChangeText={setNewItem}
                placeholder="항목 추가 · Enter로 바로 추가"
                placeholderTextColor={colors.placeholder}
                blurOnSubmit={false}
                onSubmitEditing={() => {
                  if (!newItem.trim()) return;
                  setItems((l) => [...l, { id: uid('ci'), text: newItem.trim(), done: false }]);
                  setNewItem('');
                }}
                style={[{ flex: 1, minWidth: 0, fontFamily: fonts.regular, fontSize: 15, color: colors.text }, webNoOutline]}
              />
            </View>
          </View>
          <View style={{ height: 14 }} />
          <InfoNote title="AI 연결 없음" desc="체크리스트는 보드에만 저장되고, 뉴스·공시와 연결되지 않아요." />
        </View>
      )}

      {kind === 'reference' && (
        <View style={{ gap: 14 }}>
          <SectionTitle title="참고자료 제목" hint="보드 카드 제목으로 보여요" />
          <TextField value={refTitle} onChangeText={setRefTitle} style={{ height: 48, borderRadius: 12 }} inputStyle={{ fontFamily: fonts.semibold }} />
          <SectionTitle title="자료 추가" hint="링크 붙여넣기 또는 파일 첨부" />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextField
              icon="link"
              value={url}
              onChangeText={setUrl}
              placeholder="https:// 링크를 붙여넣으세요"
              onSubmitEditing={addLink}
              autoCapitalize="none"
              keyboardType="url"
              style={{ flex: 1, height: 44, borderRadius: 12 }}
            />
            <Button label="추가" variant="secondary" size="sm" onPress={addLink} style={{ height: 44, paddingHorizontal: 18 }} />
            <Button label="파일 첨부" variant="secondary" size="sm" onPress={attachFile} style={{ height: 44, paddingHorizontal: 18 }} />
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <T size={12} color={colors.textWarm} style={{ width: 60 }}>
              종류
            </T>
            {REF_TYPES.map((t) => (
              <Hoverable
                key={t.key}
                onPress={() => setRefType(t.key)}
                style={{ height: 28, paddingHorizontal: 12, borderRadius: 14, justifyContent: 'center', backgroundColor: refType === t.key ? colors.black : colors.surfaceWarm }}
              >
                <T size={12} weight="medium" color={refType === t.key ? '#FFF' : colors.textBody} lh={1.2}>
                  {t.label}
                </T>
              </Hoverable>
            ))}
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <T size={16} weight="bold">
              추가된 자료
            </T>
            <T size={12} color={colors.textWarm}>
              {links.length}개
            </T>
          </View>
          <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 8, gap: 2 }}>
            {links.length === 0 && (
              <T size={13} color={colors.textMuted} style={{ padding: 12 }}>
                아직 추가된 자료가 없어요
              </T>
            )}
            {links.map((l) => (
              <View key={l.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 8 }}>
                <View style={{ width: 28, height: 28, borderRadius: 8, backgroundColor: '#F3F4F6', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name={l.source === 'file' ? 'file' : l.ref_type === 'news' ? 'newspaper' : 'link'} size={14} color={colors.textSub} />
                </View>
                <View style={{ flex: 1 }}>
                  <T size={14} numberOfLines={1}>
                    {l.title}
                  </T>
                  <T size={12} color={colors.textMuted}>
                    {refTypeLabel[l.ref_type]} · {l.source === 'file' ? '파일' : '링크'}
                  </T>
                </View>
                <IconButton name="external" label="열기" size={14} onPress={() => void Linking.openURL(l.url)} color={colors.textMuted} />
                <IconButton name="x" label="삭제" size={16} onPress={() => setLinks((x) => x.filter((y) => y.id !== l.id))} color={colors.textSub} />
              </View>
            ))}
          </View>
          <View style={{ height: 8 }} />
          <InfoNote title="AI 연결 없음" desc="참고자료는 보드에만 저장되고, 뉴스·공시와 연결되지 않아요." />
        </View>
      )}

      {error && (
        <T size={13} color={colors.danger} style={{ marginTop: 12 }}>
          {error}
        </T>
      )}
      <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 18, gap: 8 }}>
        {editing ? (
          <Pressable
            onPress={() =>
              remove.mutate(editing.id, {
                onSuccess: () => {
                  toast('휴지통으로 옮겼어요');
                  onClose();
                },
              })
            }
            hitSlop={8}
          >
            <T size={13} color={colors.danger}>
              휴지통으로 옮기기
            </T>
          </Pressable>
        ) : (
          <T size={12} color={colors.textWarm}>
            {footerHint}
          </T>
        )}
        <View style={{ flex: 1 }} />
        <Button label="취소" variant="secondary" onPress={onClose} style={{ paddingHorizontal: 18 }} />
        <Button label={`${KIND_TITLE[kind]} 저장`} onPress={save} loading={busy} style={{ paddingHorizontal: 24 }} />
      </View>
    </Sheet>
  );
}

function SectionTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
      <T size={16} weight="bold">
        {title}
      </T>
      {hint && (
        <T size={12} color={colors.textWarm}>
          {hint}
        </T>
      )}
    </View>
  );
}
