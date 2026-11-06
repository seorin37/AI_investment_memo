import React, { useState } from 'react';
import { Pressable, View } from 'react-native';
import { Sheet } from '@/components/ui/Modal';
import { Button, EmptyState, Hoverable, IconButton, Loading, Segmented } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { env } from '@/config/env';
import { useBoardItem, useDeleteBoardItem, useMemoTimeline, useSetAiLink, useUpdateBoardItem } from '@/hooks/queries';
import { dotDate } from '@/lib/format';
import { useUI } from '@/store/ui';
import { colors } from '@/theme/tokens';
import type { Memo } from '@/types/models';
import { AiTimeline } from './AiTimeline';
import { AiLinkCard, ColorSwatches, MemoEditArea, TagRow } from './MemoParts';

/** 메모 팝업 — [메모] 보기·수정 / [AI 업데이트] 타임라인 */
export function MemoDetailModal({ onClose, stockCode, memoId, initialTab = 'memo' }: { onClose: () => void; stockCode: string; memoId: string; initialTab?: 'memo' | 'ai' }) {
  const { data: item, isLoading } = useBoardItem(memoId);
  const memo: Memo | undefined = item?.kind === 'memo' ? item : undefined;
  const [tab, setTab] = useState<'memo' | 'ai'>(env.useRealBoard ? 'memo' : initialTab);
  const update = useUpdateBoardItem(stockCode);
  const setAi = useSetAiLink(stockCode);
  const remove = useDeleteBoardItem(stockCode);
  const toast = useUI((s) => s.showToast);

  return (
    <Sheet visible onClose={onClose} width={640} padding={24}>
      {isLoading && <Loading height={300} />}
      {!isLoading && !memo && <EmptyState title="메모를 찾을 수 없어요" desc="삭제되었거나 다른 종목의 메모예요." />}
      {memo && (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 22 }}>
            <View style={{ flex: 1, gap: 2 }}>
              <T size={12} color={colors.textWarm} tabular>
                {dotDate(memo.created_at)}
              </T>
              <T size={20} weight="bold">
                {memo.title}
              </T>
            </View>
            <Hoverable
              onPress={() => update.mutate({ id: memo.id, patch: { pinned: !memo.pinned } }, { onSuccess: () => toast(memo.pinned ? '고정을 해제했어요' : '홈에 고정했어요') })}
              style={{ height: 32, paddingHorizontal: 18, borderRadius: 10, backgroundColor: memo.pinned ? '#2E3138' : colors.surfaceWarm, justifyContent: 'center' }}
              hoverStyle={{ opacity: 0.9 }}
            >
              <T size={12} weight="medium" color={memo.pinned ? '#FFF' : colors.textBody} lh={1.2}>
                {memo.pinned ? '고정됨' : '고정'}
              </T>
            </Hoverable>
            <IconButton name="x" label="닫기" onPress={onClose} size={24} color={colors.text} box={36} />
          </View>
          <View style={{ marginBottom: 22 }}>
            <Segmented
              items={[
                { key: 'memo', label: '메모' },
                ...(env.useRealBoard
                  ? []
                  : [{ key: 'ai' as const, label: memo.unread_updates > 0 ? `AI 업데이트 · ${memo.unread_updates}` : 'AI 업데이트' }]),
              ]}
              value={tab}
              onChange={setTab}
            />
          </View>
          {tab === 'memo' ? (
            <MemoTab
              memo={memo}
              onSave={(patch, cb) =>
                update.mutate(
                  { id: memo.id, patch },
                  { onSuccess: cb, onError: (error) => toast(error.message || '메모를 저장하지 못했어요') },
                )
              }
              saving={update.isPending}
              onToggleAi={(v) =>
                setAi.mutate(
                  { memoId: memo.id, enabled: v },
                  { onError: (error) => toast(error.message || 'AI 연결 상태를 저장하지 못했어요') },
                )
              }
              onDelete={() =>
                remove.mutate(memo.id, {
                  onSuccess: () => {
                    toast('메모를 휴지통으로 옮겼어요');
                    onClose();
                  },
                  onError: (error) => toast(error.message || '메모를 삭제하지 못했어요'),
                })
              }
            />
          ) : (
            <AiTab
              memo={memo}
              onToggleAi={(v) =>
                setAi.mutate(
                  { memoId: memo.id, enabled: v },
                  { onError: (error) => toast(error.message || 'AI 연결 상태를 저장하지 못했어요') },
                )
              }
            />
          )}
        </>
      )}
    </Sheet>
  );
}

function MemoTab({
  memo,
  onSave,
  saving,
  onToggleAi,
  onDelete,
}: {
  memo: Memo;
  onSave: (patch: Partial<Pick<Memo, 'title' | 'body' | 'tags' | 'color'>>, cb?: () => void) => void;
  saving: boolean;
  onToggleAi: (v: boolean) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(memo.title);
  const [body, setBody] = useState(memo.body);

  return (
    <View style={{ gap: 14 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <T size={16} weight="bold">
          내 메모
        </T>
        {editing ? (
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <Button label="취소" variant="secondary" size="sm" onPress={() => setEditing(false)} />
            <Button label="저장" size="sm" loading={saving} disabled={!title.trim()} onPress={() => onSave({ title: title.trim(), body }, () => setEditing(false))} />
          </View>
        ) : (
          <Hoverable
            onPress={() => {
              setTitle(memo.title);
              setBody(memo.body);
              setEditing(true);
            }} style={{ height: 32, paddingHorizontal: 20, borderRadius: 10, backgroundColor: colors.surfaceWarm, justifyContent: 'center' }} hoverStyle={{ backgroundColor: '#ECE9E3' }}>
            <T size={14} weight="medium" lh={1.2}>
              수정
            </T>
          </Hoverable>
        )}
      </View>
      {editing ? (
        <MemoEditArea color={memo.color} title={title} body={body} onTitle={setTitle} onBody={setBody} />
      ) : (
        <View style={{ backgroundColor: colors.surfaceWarm, borderRadius: 16, padding: 20, minHeight: 178 }}>
          <T size={15} color={colors.textWarm} lh={1.75}>
            {memo.body || '내용 없이 제목만 남긴 메모예요.'}
          </T>
        </View>
      )}
      <TagRow tags={memo.tags} onChange={(tags) => onSave({ tags })} buttonLabel="태그 편집" />
      <ColorSwatches value={memo.color} onChange={(color) => onSave({ color })} hint="보드에 표시되는 색상" />
      <View style={{ height: 22 }} />
      <AiLinkCard value={memo.ai_linked} onChange={onToggleAi} desc="이 메모와 관련된 뉴스·공시·시장 변화를 받아요." />
      {memo.price_conditions.length > 0 && (
        <T size={12} color={colors.textWarm}>
          가격 조건 {memo.price_conditions.length}개를 코드로 감지했어요 — {memo.price_conditions.map((c) => `${(c.price / 10000).toLocaleString()}만원 ${c.direction === 'below' ? '미만' : '이상'}`).join(', ')}
        </T>
      )}
      <Pressable onPress={onDelete} hitSlop={8} style={{ alignSelf: 'flex-start', marginTop: 4 }}>
        <T size={12} color={colors.danger}>
          휴지통으로 옮기기
        </T>
      </Pressable>
    </View>
  );
}

function AiTab({ memo, onToggleAi }: { memo: Memo; onToggleAi: (v: boolean) => void }) {
  const { data, isLoading } = useMemoTimeline(memo.id);
  const [order, setOrder] = useState<'desc' | 'asc'>('desc');
  const updates = data?.entries.filter((e) => e.kind === 'update').length ?? 0;
  return (
    <View style={{ gap: 14 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <T size={16} weight="bold">
            도착한 소식
          </T>
          <T size={16} weight="bold" color={colors.greenText}>
            {updates}
          </T>
        </View>
        <Pressable onPress={() => setOrder((o) => (o === 'desc' ? 'asc' : 'desc'))} hitSlop={8}>
          <T size={12} color={colors.textWarm}>
            {order === 'desc' ? '최신순' : '오래된순'}
          </T>
        </Pressable>
      </View>
      {isLoading && <Loading />}
      {data && !memo.ai_linked && updates === 0 ? (
        <EmptyState title="AI 연결이 꺼져 있어요" desc="아래에서 AI 연결을 켜면 이 메모와 관련된 공시·뉴스·주가 변화가 여기에 도착해요." />
      ) : (
        data && <AiTimeline entries={data.entries} order={order} />
      )}
      <View style={{ height: 24 }} />
      <AiLinkCard
        value={memo.ai_linked}
        onChange={onToggleAi}
        desc={memo.ai_linked ? `이 메모를 AI가 지켜보고 있어요${data?.price_condition_count ? ` · 가격 조건 ${data.price_condition_count}개` : ''}` : '켜면 관련 소식을 받아요. 끄면 AI가 분석하지 않아요.'}
      />
    </View>
  );
}
