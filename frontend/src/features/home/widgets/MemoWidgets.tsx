/**
 * 메모 위젯 — '이상규의 위젯 아이디어' 6종 + 팀 결정 3종(메모대로 했다면 · 비교 메모 자동 카드 · 결론 낼 메모)
 */
import React, { useState } from 'react';
import { Pressable, View } from 'react-native';
import { useRouter } from 'expo-router';
import { env } from '@/config/env';
import { Icon } from '@/components/icons/Icon';
import { Button, EmptyState, Hoverable, Loading, ProgressRing, Select, SquareCheck, Switch, TextArea, TextField } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import {
  useAddChecklistItem,
  useCompareMemos,
  useConcludeCandidates,
  useConcludeMemo,
  useCreateJournal,
  useCreateMemoFor,
  useHomeChecklist,
  useJournal,
  useMarkAiUpdateRead,
  useMemoBacktests,
  useMemoUpdateSummary,
  useMyStocks,
  usePatchMemoFor,
  usePinnedMemos,
  usePriceConditions,
  useSetChecklistItem,
  useSetPriceTracking,
  useUpdateJournal,
} from '@/hooks/queries';
import { useMarketColors } from '@/hooks/useLayout';
import { dotDate, korMonthDay, mmdd, num, uid } from '@/lib/format';
import { colors, memoPalette } from '@/theme/tokens';
import type { JournalEntry, MemoColor, MemoUpdateSummary, PriceConditionRow } from '@/types/models';
import type { PinnedMemo } from '@/api';
import { LinkText, WidgetCard } from './WidgetCard';
import { FieldLabel, SuccessBox, WidgetSheet } from './WidgetSheet';

const condText = (c: { direction: 'below' | 'above'; price: number }) => `${num(c.price)}원 ${c.direction === 'below' ? '미만이면' : '이상이면'} 다시 보기`;

function MemoChip({ color, title, label }: { color: MemoColor; title: string; label?: string }) {
  return (
    <View style={{ backgroundColor: memoPalette[color].swatch, borderRadius: 8, paddingHorizontal: 10, paddingVertical: label ? 10 : 6, gap: 2 }}>
      {label && (
        <T size={10} color={colors.textWarm}>
          {label}
        </T>
      )}
      <T size={label ? 14 : 11} weight={label ? 'bold' : 'medium'} numberOfLines={1}>
        {title}
      </T>
    </View>
  );
}

// ─── 01 고정한 메모 ──────────────────────────────────────────
export function PinnedMemosWidget() {
  const { data, isLoading } = usePinnedMemos();
  const [open, setOpen] = useState<PinnedMemo | null>(null);
  return (
    <WidgetCard title="고정한 메모" subtitle="잊고 싶지 않은 내 투자 생각" icon="pin">
      {isLoading && <Loading height={80} />}
      {data?.length === 0 && <EmptyState title="고정한 메모가 없어요" desc="메모 팝업의 '고정'을 누르면 여기에 보여요." />}
      <View style={{ gap: 8 }}>
        {data?.slice(0, 3).map((m) => (
          <Hoverable key={m.id} onPress={() => setOpen(m)} style={{ backgroundColor: memoPalette[m.color].swatch, borderRadius: 10, padding: 12, gap: 2 }} hoverStyle={{ opacity: 0.9 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <T size={10} color={colors.textWarm}>
                {m.stock_name}
              </T>
              <Icon name="pin" size={11} color={colors.textWarm} />
            </View>
            <T size={14} weight="bold" numberOfLines={1}>
              {m.title}
            </T>
            <T size={11} color={colors.textWarm} numberOfLines={1}>
              {m.body.replace(/\n/g, ' ')}
            </T>
          </Hoverable>
        ))}
      </View>
      {open && <PinnedMemoSheet memo={open} onClose={() => setOpen(null)} />}
    </WidgetCard>
  );
}

function PinnedMemoSheet({ memo, onClose }: { memo: PinnedMemo; onClose: () => void }) {
  const [title, setTitle] = useState(memo.title);
  const [body, setBody] = useState(memo.body);
  const [done, setDone] = useState<'saved' | 'unpinned' | null>(null);
  const patch = usePatchMemoFor();
  if (done)
    return (
      <WidgetSheet title={done === 'saved' ? '메모를 저장했어요' : '고정을 해제했어요'} subtitle={`${memo.stock_name} · ${dotDate(memo.created_at)}`} onClose={onClose} footer={<Button label="확인" variant="blue" onPress={onClose} />}>
        <SuccessBox message={done === 'saved' ? '투자 생각을 정리해 뒀어요.' : '메모 내용은 그대로 남아 있어요.'} />
        <T size={14} weight="bold">
          {title}
        </T>
        <T size={12} color={colors.textWarm}>
          {body}
        </T>
      </WidgetSheet>
    );
  return (
    <WidgetSheet
      title="내 메모"
      subtitle={`${memo.stock_name} · ${dotDate(memo.created_at)}`}
      onClose={onClose}
      footer={
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button label="고정 해제" variant="secondary" style={{ flex: 1 }} onPress={() => patch.mutate({ id: memo.id, code: memo.stock_code, patch: { pinned: false } }, { onSuccess: () => setDone('unpinned') })} />
          <Button label="저장" variant="blue" style={{ flex: 1 }} loading={patch.isPending} disabled={!title.trim()} onPress={() => patch.mutate({ id: memo.id, code: memo.stock_code, patch: { title, body } }, { onSuccess: () => setDone('saved') })} />
        </View>
      }
    >
      <FieldLabel>제목</FieldLabel>
      <TextField value={title} onChangeText={setTitle} style={{ height: 38, borderRadius: 8 }} inputStyle={{ fontSize: 13 }} />
      <FieldLabel>메모</FieldLabel>
      <TextArea value={body} onChangeText={setBody} minHeight={150} style={{ fontSize: 13 }} />
      <T size={10} color={colors.textSub}>
        메모는 자유롭게 수정할 수 있어요.
      </T>
    </WidgetSheet>
  );
}

// ─── 02 확인할 것 ────────────────────────────────────────────
export function ChecklistWidget() {
  const { data, isLoading } = useHomeChecklist();
  const setItem = useSetChecklistItem();
  const [adding, setAdding] = useState(false);
  const shown = data?.slice(0, 4) ?? [];
  const done = shown.filter((i) => i.done).length;
  return (
    <WidgetCard title="확인할 것" subtitle="하나씩 확인하며 생각을 정리해요" right={<ProgressRing done={done} total={shown.length} size={34} color={colors.blue} dashed />}>
      {isLoading && <Loading height={80} />}
      <View>
        {shown.map((it, i) => (
          <View key={it.id} style={{ flexDirection: 'row', gap: 10, paddingVertical: 10, borderTopWidth: i ? 1 : 0, borderColor: '#EEF0F3' }}>
            <SquareCheck checked={it.done} onPress={() => setItem.mutate({ checklistId: it.checklist_id, itemId: it.id, done: !it.done, stockCode: it.stock_code })} />
            <View style={{ flex: 1 }}>
              <T size={13} color={it.done ? colors.textMuted : colors.text} strike={it.done}>
                {it.text}
              </T>
              <T size={10} color={colors.textSub}>
                {it.stock_name}
              </T>
            </View>
          </View>
        ))}
        {data && data.length > 4 && (
          <T size={11} color={colors.textMuted}>
            외 {data.length - 4}개
          </T>
        )}
      </View>
      <LinkText label="+ 확인할 것 추가" onPress={() => setAdding(true)} />
      {adding && <AddChecklistSheet onClose={() => setAdding(false)} />}
    </WidgetCard>
  );
}

function AddChecklistSheet({ onClose }: { onClose: () => void }) {
  const { data: stocks = [] } = useMyStocks();
  const [code, setCode] = useState<string | null>(stocks[0]?.code ?? null);
  const [text, setText] = useState('');
  const [added, setAdded] = useState(false);
  const add = useAddChecklistItem();
  const { data: items = [] } = useHomeChecklist();
  const name = stocks.find((s) => s.code === code)?.name ?? '';
  if (added) {
    const mine = items.filter((i) => i.stock_code === code);
    return (
      <WidgetSheet title="확인할 것을 추가했어요" subtitle="기업별로 확인할 내용을 정리해요" onClose={onClose} footer={<Button label="확인" variant="blue" onPress={onClose} />}>
        <ProgressRing done={mine.filter((i) => i.done).length} total={mine.length} size={30} color={colors.blue} dashed />
        <T size={15} weight="bold">
          {text}
        </T>
        <T size={11} color={colors.textSub}>
          {name}
        </T>
        <T size={12} color={colors.textWarm}>
          체크리스트에 새 항목을 남겼어요.
        </T>
      </WidgetSheet>
    );
  }
  return (
    <WidgetSheet
      title="확인할 것 추가"
      subtitle="기업별로 확인할 내용을 정리해요"
      onClose={onClose}
      footer={
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button label="취소" variant="secondary" style={{ flex: 1 }} onPress={onClose} />
          <Button label="추가" variant="blue" style={{ flex: 1 }} disabled={!code || !text.trim()} loading={add.isPending} onPress={() => code && add.mutate({ stockCode: code, text: text.trim() }, { onSuccess: () => setAdded(true) })} />
        </View>
      }
    >
      <FieldLabel>종목</FieldLabel>
      <Select value={code} options={stocks.map((s) => ({ key: s.code, label: s.name }))} onChange={setCode} />
      <FieldLabel>확인할 내용</FieldLabel>
      <TextField value={text} onChangeText={setText} placeholder="예: 다음 분기 실적 확인" style={{ height: 38, borderRadius: 8 }} inputStyle={{ fontSize: 13 }} />
      <T size={10} color={colors.textSub}>
        간단한 확인 항목도 자유롭게 추가해요.
      </T>
    </WidgetSheet>
  );
}

// ─── 03 빠른 메모 ────────────────────────────────────────────
export function QuickMemoWidget() {
  const { data: stocks = [] } = useMyStocks();
  const [code, setCode] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [result, setResult] = useState<{ id: string; code: string; body: string } | null>(null);
  const create = useCreateMemoFor();
  const target = code ?? stocks[0]?.code ?? null;

  const submit = () => {
    if (!target || !text.trim()) return;
    const body = text.trim();
    const firstLine = body.split('\n')[0];
    create.mutate(
      { code: target, input: { title: firstLine.length > 28 ? `${firstLine.slice(0, 28)}…` : firstLine, body, tags: [], color: 'yellow', ai_linked: false } },
      {
        onSuccess: (m) => {
          setResult({ id: m.id, code: target, body });
          setText('');
        },
      },
    );
  };

  return (
    <WidgetCard title="빠른 메모" subtitle="떠오른 생각을 놓치기 전에" icon="edit">
      <Select value={target} options={stocks.map((s) => ({ key: s.code, label: s.name }))} onChange={setCode} placeholder="종목 선택" />
      <TextArea value={text} onChangeText={setText} placeholder="지금 떠오른 생각을 자유롭게 남겨보세요." minHeight={72} style={{ fontSize: 13, padding: 12 }} />
      <Button label="메모 남기기" variant="blue" size="sm" style={{ height: 36 }} onPress={submit} loading={create.isPending} disabled={!text.trim() || !target} />
      <T size={10} color={colors.textSub}>
        남긴 메모는 선택한 종목의 메모 보드에 모여요.
      </T>
      {result && <QuickMemoDoneSheet result={result} stockName={stocks.find((s) => s.code === result.code)?.name ?? ''} onClose={() => setResult(null)} />}
    </WidgetCard>
  );
}

function QuickMemoDoneSheet({ result, stockName, onClose }: { result: { id: string; code: string; body: string }; stockName: string; onClose: () => void }) {
  const [pinned, setPinned] = useState(false);
  const patch = usePatchMemoFor();
  return (
    <WidgetSheet
      title={pinned ? '홈에 고정했어요' : '메모를 남겼어요'}
      subtitle={stockName}
      onClose={onClose}
      footer={
        pinned ? (
          <Button label="확인" variant="blue" onPress={onClose} />
        ) : (
          <>
            <Button label="홈에 고정" variant="secondary" onPress={() => patch.mutate({ id: result.id, code: result.code, patch: { pinned: true } }, { onSuccess: () => setPinned(true) })} loading={patch.isPending} />
            <Button label="새 메모 쓰기" variant="blue" onPress={onClose} />
          </>
        )
      }
    >
      <SuccessBox message={pinned ? '중요한 생각을 홈에 붙여 뒀어요.' : `${stockName}에 메모를 남겼어요.`} />
      <T size={13} color={colors.textBody} lh={1.6}>
        {result.body}
      </T>
      <T size={10} color={colors.textSub}>
        이 메모는 {stockName} 메모 보드에서 다시 볼 수 있어요.
      </T>
    </WidgetSheet>
  );
}

// ─── 04 지켜보는 가격 조건 ───────────────────────────────────
export function PriceConditionWidget() {
  const { data, isLoading } = usePriceConditions();
  const setTracking = useSetPriceTracking();
  const [open, setOpen] = useState<PriceConditionRow | null>(null);
  const statusLabel = (r: PriceConditionRow) =>
    !r.condition.tracking ? { t: '일시 중지', c: colors.textSub } : r.condition.status === 'reached' ? { t: '조건 도달', c: colors.greenText } : { t: '기다리는 중', c: colors.textSub };
  return (
    <WidgetCard title="지켜보는 가격 조건" subtitle="내가 정한 기준과 지금의 거리" icon="bellRing">
      {isLoading && <Loading height={80} />}
      {data?.length === 0 && <EmptyState title="가격 조건 메모가 없어요" desc="“15만원 밑이면 다시 보기”처럼 적으면 자동으로 인식해요." />}
      <View style={{ gap: 8 }}>
        {data?.map((r) => {
          const s = statusLabel(r);
          return (
            <Hoverable key={r.condition.id} onPress={() => setOpen(r)} style={{ backgroundColor: colors.surfaceSubtle, borderRadius: 10, padding: 12, gap: 2 }} hoverStyle={{ backgroundColor: '#EEF0F3' }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <T size={10} color={colors.textSub}>
                  {r.stock_name}
                </T>
                <T size={10} weight="medium" color={s.c}>
                  {s.t}
                </T>
              </View>
              <T size={12} weight="medium">
                {condText(r.condition)}
              </T>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <T size={18} weight="bold" tabular>
                  {num(r.current_price)}원
                </T>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <Switch tone="blue" value={r.condition.tracking} onChange={(v) => setTracking.mutate({ memoId: r.memo_id, conditionId: r.condition.id, tracking: v })} />
                  <Icon name="chevronRight" size={14} color={colors.textBody} />
                </View>
              </View>
            </Hoverable>
          );
        })}
      </View>
      <T size={10} color={colors.textSub}>
        {env.useMock ? '예시 시세 · 실시간 가격이 아니에요.' : '종가 기준 · 실시간 가격이 아니에요.'}
      </T>
      {open && <PriceConditionSheet row={open} onClose={() => setOpen(null)} />}
    </WidgetCard>
  );
}

function PriceConditionSheet({ row, onClose }: { row: PriceConditionRow; onClose: () => void }) {
  const reached = row.condition.status === 'reached';
  const gap = row.current_price - row.condition.price;
  return (
    <WidgetSheet title="가격 조건 상세" subtitle={row.stock_name} onClose={onClose} footer={<Button label="확인" variant="blue" onPress={onClose} />}>
      <View style={{ backgroundColor: reached ? colors.greenSoft : colors.blueSoft, borderRadius: 12, padding: 16, gap: 6 }}>
        <T size={13} weight="semibold" color={reached ? colors.greenText : colors.blue}>
          {reached ? '설정한 가격 조건에 도달했어요' : !row.condition.tracking ? '가격 조건 추적이 꺼져 있어요' : '설정한 가격을 기다리고 있어요'}
        </T>
        <T size={22} weight="bold" tabular>
          현재가 {num(row.current_price)}원
        </T>
        <T size={12} color={colors.textSub}>
          기준: {num(row.condition.price)}원 {row.condition.direction === 'below' ? '미만' : '이상'}
        </T>
      </View>
      <T size={12} color={colors.textBody}>
        설정한 기준보다 {num(Math.abs(gap))}원 {gap >= 0 ? '높아요' : '낮아요'}.
      </T>
      <View style={{ backgroundColor: '#DEF5E3', borderRadius: 12, padding: 14, gap: 4 }}>
        <T size={10} color={colors.textWarm}>
          가격 조건을 남긴 내 메모
        </T>
        <T size={14} weight="bold">
          {row.memo_title}
        </T>
      </View>
      <T size={10} color={colors.textSub}>
        {env.useMock ? '예시 시세입니다. ' : ''}가격 조건 추적을 꺼도 원래 메모는 남아요.
      </T>
    </WidgetSheet>
  );
}

// ─── 05 최근 투자 기록 ───────────────────────────────────────
export function RecentJournalWidget() {
  const { data, isLoading } = useJournal();
  const [sheet, setSheet] = useState<JournalEntry | 'new' | null>(null);
  return (
    <WidgetCard title="최근 투자 기록" subtitle="그때의 판단을 다시 돌아봐요" icon="plus" onIconPress={() => setSheet('new')}>
      {isLoading && <Loading height={80} />}
      <View>
        {data?.slice(0, 2).map((j, i) => (
          <Hoverable key={j.id} onPress={() => setSheet(j)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderTopWidth: i ? 1 : 0, borderBottomWidth: 1, borderColor: '#EEF0F3' }} hoverStyle={{ backgroundColor: '#FAFAFB' }}>
            <View style={{ width: 40, height: 36, borderRadius: 8, backgroundColor: colors.surfaceSubtle, alignItems: 'center', justifyContent: 'center' }}>
              <T size={10} color={colors.textBody} tabular>
                {mmdd(j.created_at)}
              </T>
            </View>
            <View style={{ flex: 1 }}>
              <T size={13} weight="semibold" numberOfLines={1}>
                {j.title || '새로운 기록'}
              </T>
              <T size={10} color={colors.textSub}>
                {j.stock_name ?? '종목 없음'} · 투자 기록
              </T>
            </View>
            <Icon name="chevronRight" size={14} color={colors.textBody} />
          </Hoverable>
        ))}
      </View>
      <LinkText label="오늘의 생각 기록하기" onPress={() => setSheet('new')} />
      {sheet && <JournalSheet entry={sheet === 'new' ? null : sheet} onClose={() => setSheet(null)} />}
    </WidgetCard>
  );
}

function JournalSheet({ entry, onClose }: { entry: JournalEntry | null; onClose: () => void }) {
  const { data: stocks = [] } = useMyStocks();
  const [code, setCode] = useState<string | null>(entry?.stock_code ?? stocks[0]?.code ?? null);
  const [title, setTitle] = useState(entry?.title ?? '');
  const firstText = entry?.blocks.filter((b) => b.type === 'paragraph').map((b) => ('text' in b ? b.text : '')).join('\n\n') ?? '';
  const [body, setBody] = useState(firstText);
  const [saved, setSaved] = useState(false);
  const create = useCreateJournal();
  const update = useUpdateJournal();
  const name = stocks.find((s) => s.code === code)?.name ?? '';
  const save = () => {
    const blocks = body
      .split(/\n{2,}/)
      .filter((t) => t.trim())
      .map((text) => ({ id: uid('b'), type: 'paragraph' as const, text }));
    if (entry) {
      const others = entry.blocks.filter((b) => b.type !== 'paragraph');
      update.mutate({ id: entry.id, patch: { title, stock_code: code, blocks: [...blocks, ...others] } }, { onSuccess: () => setSaved(true) });
    } else create.mutate({ title, stock_code: code, blocks }, { onSuccess: () => setSaved(true) });
  };
  if (saved)
    return (
      <WidgetSheet title="투자 기록을 저장했어요" subtitle={`${name} · 메모와 별도로 보관해요`} onClose={onClose} footer={<Button label="확인" variant="blue" onPress={onClose} />}>
        <SuccessBox message="오늘의 판단을 남겨 뒀어요." />
        <T size={14} weight="bold">
          {title}
        </T>
        <T size={12} color={colors.textWarm}>
          이 기록은 {name}의 투자 기록에만 저장돼요. 메모와 AI 추적 항목은 바뀌지 않아요.
        </T>
      </WidgetSheet>
    );
  return (
    <WidgetSheet title={entry ? '투자 기록' : '새 투자 기록'} subtitle={name} onClose={onClose} footer={<Button label="기록 저장" variant="blue" onPress={save} loading={create.isPending || update.isPending} disabled={!title.trim()} />}>
      <FieldLabel>종목</FieldLabel>
      <Select value={code} options={stocks.map((s) => ({ key: s.code, label: s.name }))} onChange={setCode} />
      <FieldLabel>기록 제목</FieldLabel>
      <TextField value={title} onChangeText={setTitle} placeholder="오늘의 판단을 한 문장으로" style={{ height: 38, borderRadius: 8 }} inputStyle={{ fontSize: 13 }} />
      <FieldLabel>내 투자 기록</FieldLabel>
      <TextArea value={body} onChangeText={setBody} placeholder="무엇을 보고, 어떤 생각으로 판단했나요?" minHeight={140} style={{ fontSize: 13 }} />
      <T size={10} color={colors.textSub}>
        선택한 종목의 투자 기록으로 보관해요. 메모와는 별개예요.
      </T>
    </WidgetSheet>
  );
}

// ─── 06 종목별 업데이트 (연결된 메모까지) ──────────────────────
export function MemoUpdatesWidget() {
  const { data, isLoading } = useMemoUpdateSummary();
  const [open, setOpen] = useState<MemoUpdateSummary | null>(null);
  const total = data?.reduce((n, s) => n + s.new_count, 0) ?? 0;
  return (
    <WidgetCard title="종목별 업데이트" subtitle="연결된 메모까지 한눈에" icon="sparkles">
      {isLoading && <Loading height={80} />}
      {data?.length === 0 && <EmptyState title="새 소식이 없어요" desc="AI 연결을 켠 메모에 소식이 오면 여기에 보여요." />}
      <View style={{ gap: 8 }}>
        {data?.map((s) => (
          <Hoverable key={s.stock_code} onPress={() => setOpen(s)} style={{ backgroundColor: colors.surfaceSubtle, borderRadius: 10, padding: 12, gap: 8 }} hoverStyle={{ backgroundColor: '#EEF0F3' }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <T size={13} weight="bold">
                {s.stock_name}
              </T>
              <T size={10} color={colors.blue}>
                새 소식 {s.new_count}
              </T>
            </View>
            {s.memos.slice(0, 2).map((m) => (
              <MemoChip key={m.memo_id} color={m.color} title={m.title} />
            ))}
          </Hoverable>
        ))}
      </View>
      {total > 0 && <LinkText label={`내 메모에 도착한 새 소식 ${total}개`} onPress={() => data?.[0] && setOpen(data[0])} align="left" />}
      {open && <MemoUpdatesSheet summary={open} onClose={() => setOpen(null)} />}
    </WidgetCard>
  );
}

function MemoUpdatesSheet({ summary, onClose }: { summary: MemoUpdateSummary; onClose: () => void }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const markRead = useMarkAiUpdateRead(summary.stock_code);
  const router = useRouter();
  const typeLabel = { news: '뉴스', disclosure: '공시', price: '주가' } as const;
  return (
    <WidgetSheet
      title="메모에 도착한 소식"
      subtitle={`${summary.stock_name} · AI 업데이트`}
      onClose={onClose}
      footer={
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button
            label="보드에서 보기"
            variant="secondary"
            style={{ flex: 1 }}
            onPress={() => {
              onClose();
              router.navigate(`/stocks/${summary.stock_code}`);
            }}
          />
          <Button label="확인" variant="secondary" style={{ flex: 1 }} onPress={onClose} />
        </View>
      }
    >
      {summary.memos.map((m) => (
        <View key={m.memo_id} style={{ gap: 8 }}>
          <MemoChip color={m.color} title={m.title} label="이 메모와 연결했어요" />
          {m.updates.map((u) => {
            const on = expanded === u.id;
            return (
              <Pressable
                key={u.id}
                onPress={() => {
                  setExpanded(on ? null : u.id);
                  if (!u.read) markRead.mutate(u.id);
                }}
                style={{ borderRadius: 10, borderWidth: 1, borderColor: '#EEF0F3', backgroundColor: colors.surfaceSubtle, padding: 12, gap: 4 }}
              >
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <T size={13} weight="semibold" style={{ flex: 1 }}>
                    {u.headline}
                  </T>
                  <Icon name={on ? 'chevronDown' : 'chevronRight'} size={14} color={colors.textBody} />
                </View>
                <T size={10} color={colors.textSub}>
                  {typeLabel[u.type]} · AI가 정리한 {env.useMock ? '예시' : '요약'}
                </T>
                {on && (
                  <T size={12} color={colors.textBody} lh={1.6}>
                    {u.summary}
                  </T>
                )}
              </Pressable>
            );
          })}
        </View>
      ))}
      <T size={10} color={colors.textSub}>
        AI가 내 메모와 관련된 내용을 정리했어요. 실제 뉴스·공시는 서비스에서 원문으로 연결해요.
      </T>
    </WidgetSheet>
  );
}

// ─── 07 메모대로 했다면 (팀 결정) ────────────────────────────
export function MemoBacktestWidget() {
  const { data, isLoading } = useMemoBacktests();
  const mc = useMarketColors();
  return (
    <WidgetCard title="메모대로 했다면" subtitle="행동 조건 메모를 실제 주가로 검증해요" icon="history">
      {isLoading && <Loading height={80} />}
      {data?.length === 0 && <EmptyState title="검증할 조건 메모가 없어요" desc="“○○원 밑이면 매수” 같은 메모를 남겨 보세요." />}
      <View style={{ gap: 8 }}>
        {data?.map((b) => (
          <View key={b.condition.id} style={{ backgroundColor: colors.surfaceSubtle, borderRadius: 10, padding: 12, gap: 4 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <T size={10} color={colors.textSub}>
                {b.stock_name}
              </T>
              <T size={10} weight="medium" color={b.triggered_at ? colors.greenText : colors.textSub}>
                {b.triggered_at ? `${mmdd(b.triggered_at)} 조건 도달` : '조건 대기'}
              </T>
            </View>
            <T size={13} weight="semibold" numberOfLines={1}>
              {b.memo_title}
            </T>
            {b.return_pct !== null && b.trigger_price ? (
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' }}>
                <T size={11} color={colors.textSub} tabular>
                  {num(b.trigger_price)}원 → 지금 {num(b.current_price)}원
                </T>
                <T size={18} weight="bold" color={mc.of(b.return_pct)} tabular>
                  {b.return_pct > 0 ? '+' : ''}
                  {b.return_pct.toFixed(1)}%
                </T>
              </View>
            ) : (
              <T size={11} color={colors.textSub} tabular>
                아직 조건에 닿지 않았어요 · {num(Math.abs(b.current_price - b.condition.price))}원 남음
              </T>
            )}
          </View>
        ))}
      </View>
      <T size={10} color={colors.textSub}>
        조건 도달일 종가 기준 단순 계산이에요. 투자 권유가 아니에요.
      </T>
    </WidgetCard>
  );
}

// ─── 08 비교 메모 자동 카드 (팀 결정) ─────────────────────────
export function CompareMemoWidget() {
  const { data, isLoading } = useCompareMemos();
  const mc = useMarketColors();
  const card = data?.[0];
  const rows: { label: string; get: (s: NonNullable<typeof card>['left']) => string; better?: 'high' | 'low'; raw?: (s: NonNullable<typeof card>['left']) => number }[] = [
    { label: '현재가', get: (s) => `${num(s.price)}원` },
    { label: '1개월 수익률', get: (s) => `${s.return_1m > 0 ? '+' : ''}${s.return_1m.toFixed(1)}%`, raw: (s) => s.return_1m, better: 'high' },
    { label: 'PER', get: (s) => (s.per ? `${s.per.toFixed(2)}배` : '—'), raw: (s) => s.per ?? Infinity, better: 'low' },
    { label: 'PBR', get: (s) => (s.pbr ? `${s.pbr.toFixed(2)}배` : '—'), raw: (s) => s.pbr ?? Infinity, better: 'low' },
    { label: '영업이익률', get: (s) => `${s.operating_margin.toFixed(1)}%`, raw: (s) => s.operating_margin, better: 'high' },
    { label: 'ROE', get: (s) => `${s.roe.toFixed(1)}%`, raw: (s) => s.roe, better: 'high' },
    { label: '부채비율', get: (s) => `${s.debt_ratio}%`, raw: (s) => s.debt_ratio, better: 'low' },
  ];
  return (
    <WidgetCard title="비교 메모 자동 카드" subtitle="‘비교해보기’ 메모에 두 기업 지표를 나란히" icon="scale">
      {isLoading && <Loading height={80} />}
      {!isLoading && !card && <EmptyState title="비교 메모가 없어요" desc="“삼성전자랑 같이 비교해보기”처럼 메모를 남기면 자동으로 카드가 생겨요." />}
      {card && (
        <>
          <MemoChip color="purple" title={card.memo_title} />
          <View>
            <View style={{ flexDirection: 'row', paddingBottom: 8, borderBottomWidth: 1, borderColor: '#EEF0F3' }}>
              <View style={{ flex: 1.1 }} />
              <T size={12} weight="bold" style={{ flex: 1, textAlign: 'right' }}>
                {card.left.stock_name}
              </T>
              <T size={12} weight="bold" style={{ flex: 1, textAlign: 'right' }}>
                {card.right.stock_name}
              </T>
            </View>
            {rows.map((r) => {
              const lv = r.raw?.(card.left);
              const rv = r.raw?.(card.right);
              const leftWins = r.better && lv !== undefined && rv !== undefined && (r.better === 'high' ? lv > rv : lv < rv);
              const rightWins = r.better && lv !== undefined && rv !== undefined && (r.better === 'high' ? rv > lv : rv < lv);
              const colorFor = (s: typeof card.left) => (r.label === '1개월 수익률' ? mc.of(s.return_1m) : colors.text);
              return (
                <View key={r.label} style={{ flexDirection: 'row', paddingVertical: 7, borderBottomWidth: 1, borderColor: '#F3F4F6' }}>
                  <T size={11} color={colors.textSub} style={{ flex: 1.1 }}>
                    {r.label}
                  </T>
                  <T size={12} weight={leftWins ? 'bold' : 'regular'} color={colorFor(card.left)} style={{ flex: 1, textAlign: 'right' }} tabular>
                    {r.get(card.left)}
                  </T>
                  <T size={12} weight={rightWins ? 'bold' : 'regular'} color={colorFor(card.right)} style={{ flex: 1, textAlign: 'right' }} tabular>
                    {r.get(card.right)}
                  </T>
                </View>
              );
            })}
          </View>
          <T size={10} color={colors.textSub}>
            굵게 표시된 값이 해당 지표에서 상대적으로 유리해요.
          </T>
        </>
      )}
    </WidgetCard>
  );
}

// ─── 09 결론 낼 메모 (팀 결정) ───────────────────────────────
export function ConcludeMemoWidget() {
  const { data, isLoading } = useConcludeCandidates();
  const [open, setOpen] = useState<NonNullable<typeof data>[number] | null>(null);
  return (
    <WidgetCard title="결론 낼 메모" subtitle="전제가 이미 일어난 메모에 결론을 남겨요" icon="flag">
      {isLoading && <Loading height={80} />}
      {data?.length === 0 && <EmptyState title="결론 낼 메모가 없어요" desc="메모의 전제(실적 발표, 가격 도달 등)가 일어나면 여기로 와요." />}
      <View style={{ gap: 8 }}>
        {data?.map((c) => (
          <View key={c.memo_id} style={{ backgroundColor: colors.surfaceSubtle, borderRadius: 10, padding: 12, gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Icon name="check" size={12} color={colors.greenText} strokeWidth={2.6} />
              <T size={11} weight="medium" color={colors.greenText} style={{ flex: 1 }} numberOfLines={1}>
                {c.premise_event}
              </T>
              <T size={10} color={colors.textSub}>
                {korMonthDay(c.occurred_at)}
              </T>
            </View>
            <MemoChip color={c.color} title={`${c.stock_name} · ${c.memo_title}`} />
            <Button label="결론 쓰기" size="sm" variant="outline" onPress={() => setOpen(c)} style={{ alignSelf: 'flex-start' }} />
          </View>
        ))}
      </View>
      {open && <ConcludeSheet candidate={open} onClose={() => setOpen(null)} />}
    </WidgetCard>
  );
}

function ConcludeSheet({ candidate, onClose }: { candidate: NonNullable<ReturnType<typeof useConcludeCandidates>['data']>[number]; onClose: () => void }) {
  const [text, setText] = useState('');
  const [done, setDone] = useState(false);
  const conclude = useConcludeMemo();
  const router = useRouter();
  if (done)
    return (
      <WidgetSheet
        title="투자 기록으로 보냈어요"
        subtitle={candidate.stock_name}
        onClose={onClose}
        footer={
          <Button
            label="투자 기록에서 보기"
            variant="blue"
            onPress={() => {
              onClose();
              router.navigate('/journal');
            }}
          />
        }
      >
        <SuccessBox message="메모를 마무리하고 결론을 기록했어요." />
        <T size={12} color={colors.textWarm}>
          처음 메모와 내 결론이 함께 투자 기록에 남았어요. 보드에서는 메모가 정리돼요.
        </T>
      </WidgetSheet>
    );
  return (
    <WidgetSheet
      title="결론 쓰기"
      subtitle={`${candidate.stock_name} · ${candidate.premise_event}`}
      onClose={onClose}
      footer={<Button label="투자 기록으로 보내기" variant="blue" disabled={!text.trim()} loading={conclude.isPending} onPress={() => conclude.mutate({ memoId: candidate.memo_id, stockCode: candidate.stock_code, conclusion: text.trim() }, { onSuccess: () => setDone(true) })} />}
    >
      <MemoChip color={candidate.color} title={candidate.memo_title} label="처음 남긴 메모" />
      <T size={12} color={colors.textWarm}>
        {candidate.memo_body}
      </T>
      <FieldLabel>내 결론</FieldLabel>
      <TextArea value={text} onChangeText={setText} placeholder="전제가 일어난 지금, 처음 생각과 비교해 어떻게 판단했나요?" minHeight={140} style={{ fontSize: 13 }} />
    </WidgetSheet>
  );
}
