import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, PanResponder, Platform, View, type LayoutRectangle } from 'react-native';
import Svg, { Defs, Path, Pattern, Rect } from 'react-native-svg';
import { Page, PageHeader } from '@/components/layout/Page';
import { Icon, type IconName } from '@/components/icons/Icon';
import { Sheet, SheetHeader } from '@/components/ui/Modal';
import { Button, Hoverable, Loading } from '@/components/ui/primitives';
import { T } from '@/components/ui/Text';
import { useHomeLayout, useSaveHomeLayout } from '@/hooks/queries';
import { useBreakpoint } from '@/hooks/useLayout';
import { uid } from '@/lib/format';
import { colors, shadow } from '@/theme/tokens';
import type { HomeLayout, WidgetInstance, WidgetType } from '@/types/models';
import { TEMPLATE_WIDGETS, WIDGETS, widgetDef } from './registry';
import { CalendarWidget, MarketWidget, NewsWidget, UpdatesWidget } from './widgets/MarketWidgets';

/** 2. 홈 — 시작 설정(2.0) · 기본 템플릿(2.1) · 직접 사용자화(2.2 / 2.4.x) */
export function HomeScreen() {
  const { data: layout, isLoading } = useHomeLayout();
  const save = useSaveHomeLayout();
  const [editing, setEditing] = useState(false);

  if (isLoading || !layout) return <Loading height={500} />;
  const set = (l: HomeLayout) => save.mutate(l);

  if (layout.mode === 'unset')
    return (
      <HomeOnboarding
        onTemplate={() => set({ mode: 'template', widgets: TEMPLATE_WIDGETS })}
        onCustom={() => {
          set({ mode: 'custom', widgets: [] });
          setEditing(true);
        }}
      />
    );
  if (layout.mode === 'template')
    return (
      <TemplateHome
        onEdit={() => {
          set({ mode: 'custom', widgets: layout.widgets.length ? layout.widgets : TEMPLATE_WIDGETS });
          setEditing(true);
        }}
      />
    );
  return (
    <CustomHome
      widgets={layout.widgets}
      editing={editing || layout.widgets.length === 0}
      setEditing={setEditing}
      onChange={(widgets) => set({ mode: 'custom', widgets })}
      onReset={() => {
        setEditing(false);
        set({ mode: 'unset', widgets: [] });
      }}
    />
  );
}

// ─── 2.0 시작 설정 ───────────────────────────────────────────
function HomeOnboarding({ onTemplate, onCustom }: { onTemplate: () => void; onCustom: () => void }) {
  const { isMobile } = useBreakpoint();
  return (
    <Page top={isMobile ? 24 : 160}>
      <View style={{ alignItems: 'center', gap: 12 }}>
        <View style={{ backgroundColor: '#F1F2F4', borderRadius: 16, paddingHorizontal: 16, height: 30, justifyContent: 'center' }}>
          <T size={12} weight="medium" lh={1}>
            처음 시작하기
          </T>
        </View>
        <T size={isMobile ? 24 : 32} weight="bold" align="center">
          나에게 맞는 홈 화면을 선택해 주세요
        </T>
        <T size={15} color={colors.textSub} align="center">
          추천 템플릿을 바로 적용하거나, 원하는 정보로 직접 구성할 수 있어요.
        </T>
      </View>
      <View style={{ flexDirection: isMobile ? 'column' : 'row', gap: 24, marginTop: 36, alignSelf: 'center', width: '100%', maxWidth: 960 }}>
        <ChoiceCard
          recommended
          icon="grid"
          title="기본 템플릿 적용"
          desc="시장 흐름과 내 종목 소식을 한눈에 보는 추천 구성을 바로 시작해요."
          points={['시장 지수와 환율', '관심 종목 업데이트', '주요 일정과 뉴스']}
          cta="템플릿으로 시작"
          onPress={onTemplate}
        />
        <ChoiceCard icon="sliders" title="직접 사용자화" desc="보고 싶은 정보만 골라 나만의 홈 화면을 직접 구성해요." points={['원하는 위젯 선택', '위젯 순서와 크기 조정', '언제든 다시 변경']} cta="직접 구성하기" onPress={onCustom} />
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 28 }}>
        <Icon name="info" size={14} color={colors.textMuted} />
        <T size={13} color={colors.textMuted}>
          선택한 설정은 홈 화면에서 언제든 변경할 수 있어요.
        </T>
      </View>
    </Page>
  );
}

function ChoiceCard({ recommended, icon, title, desc, points, cta, onPress }: { recommended?: boolean; icon: IconName; title: string; desc: string; points: string[]; cta: string; onPress: () => void }) {
  return (
    <Hoverable
      onPress={onPress}
      style={{ flex: 1, borderRadius: 20, borderWidth: recommended ? 2 : 1, borderColor: recommended ? colors.black : colors.border, backgroundColor: recommended ? '#F7F8FA' : colors.surface, padding: 28, gap: 14 }}
      hoverStyle={{ ...shadow.pop }}
    >
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <View style={{ width: 48, height: 48, borderRadius: 12, backgroundColor: recommended ? '#ECEDF0' : '#F5F6F8', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={icon} size={22} color={colors.text} />
        </View>
        {recommended && (
          <View style={{ backgroundColor: colors.black, borderRadius: 14, paddingHorizontal: 12, height: 28, justifyContent: 'center' }}>
            <T size={12} weight="bold" color="#FFF" lh={1}>
              추천
            </T>
          </View>
        )}
      </View>
      <T size={21} weight="bold" style={{ marginTop: 6 }}>
        {title}
      </T>
      <T size={14} color={colors.textSub}>
        {desc}
      </T>
      <View style={{ gap: 12, marginTop: 18, marginBottom: 16 }}>
        {points.map((p) => (
          <View key={p} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={{ width: 18, height: 18, borderRadius: 9, backgroundColor: '#ECEDF0', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="check" size={11} color={colors.text} strokeWidth={2.5} />
            </View>
            <T size={13}>{p}</T>
          </View>
        ))}
      </View>
      <Button label={cta} variant={recommended ? 'primary' : 'secondary'} onPress={onPress} style={!recommended ? { backgroundColor: '#F5F6F8' } : undefined} />
    </Hoverable>
  );
}

// ─── 2.1 기본 템플릿 ─────────────────────────────────────────
function TemplateHome({ onEdit }: { onEdit: () => void }) {
  const { isDesktop, isMobile } = useBreakpoint();
  return (
    <Page top={56}>
      <PageHeader title="홈" subtitle="시장 흐름과 내 종목 소식을 한눈에 확인하세요." right={<Button label="홈 편집" variant="outline" size="sm" icon="sliders" onPress={onEdit} />} />
      <View style={{ flexDirection: isDesktop ? 'row' : 'column', gap: 24 }}>
        <View style={{ flex: 1, gap: 24, minWidth: 0 }}>
          <View style={{ gap: 14 }}>
            <T size={16} weight="semibold">
              시장 한눈에 보기
            </T>
            <MarketWidget />
          </View>
          <View style={{ flexDirection: isMobile ? 'column' : 'row', gap: 24 }}>
            <View style={{ width: isMobile ? undefined : 248 }}>
              <UpdatesWidget />
            </View>
            <View style={{ flex: 1 }}>
              <CalendarWidget />
            </View>
          </View>
        </View>
        <View style={{ width: isDesktop ? 318 : undefined }}>
          <NewsWidget />
        </View>
      </View>
    </Page>
  );
}

// ─── 2.2 직접 사용자화 ───────────────────────────────────────
function CustomHome({
  widgets,
  editing,
  setEditing,
  onChange,
  onReset,
}: {
  widgets: WidgetInstance[];
  editing: boolean;
  setEditing: (v: boolean) => void;
  onChange: (w: WidgetInstance[]) => void;
  onReset: () => void;
}) {
  const { isMobile, isDesktop } = useBreakpoint();
  const [gridW, setGridW] = useState(0);
  const [picker, setPicker] = useState(false);
  const rects = useRef(new Map<string, LayoutRectangle>());
  const cols = isMobile ? 1 : isDesktop ? 4 : 2;
  const GAP = 24;
  const colW = gridW > 0 ? (gridW - GAP * (cols - 1)) / cols : 0;
  const widthOf = (span: number) => {
    const s = Math.min(span, cols);
    return s * colW + (s - 1) * GAP;
  };

  const move = (id: string, dx: number, dy: number) => {
    const r = rects.current.get(id);
    if (!r) return;
    const cx = r.x + r.width / 2 + dx;
    const cy = r.y + r.height / 2 + dy;
    let target: string | null = null;
    let best = Infinity;
    rects.current.forEach((rr, key) => {
      if (key === id || !widgets.some((w) => w.id === key)) return;
      const inside = cx >= rr.x && cx <= rr.x + rr.width && cy >= rr.y && cy <= rr.y + rr.height;
      const d = Math.hypot(cx - (rr.x + rr.width / 2), cy - (rr.y + rr.height / 2));
      if (inside) {
        target = key;
        best = -1;
      } else if (best !== -1 && d < best && d < Math.max(rr.width, rr.height)) {
        best = d;
        target = key;
      }
    });
    if (!target) return;
    const from = widgets.findIndex((w) => w.id === id);
    const to = widgets.findIndex((w) => w.id === target);
    const next = [...widgets];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  };

  const resize = (id: string) =>
    onChange(
      widgets.map((w) => {
        if (w.id !== id) return w;
        const spans = widgetDef(w.type).spans;
        const i = spans.indexOf(w.span);
        return { ...w, span: spans[(i + 1) % spans.length] };
      }),
    );

  const add = (type: WidgetType) => {
    const def = widgetDef(type);
    onChange([...widgets, { id: uid('w'), type, span: def.defaultSpan }]);
    setPicker(false);
  };

  return (
    <Page top={editing ? 48 : 56}>
      <PageHeader
        title={editing ? '홈 직접 사용자화' : '홈'}
        subtitle={editing ? '필요한 위젯을 추가해 나만의 투자 홈을 만들어 보세요.' : '내가 고른 위젯으로 구성한 홈이에요.'}
        size={28}
        right={
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {editing ? (
              <>
                <Button label="시작 화면으로" variant="outline" onPress={onReset} style={{ borderRadius: 12 }} />
                {widgets.length > 0 && <Button label="완료" onPress={() => setEditing(false)} style={{ borderRadius: 12 }} />}
              </>
            ) : (
              <Button label="홈 편집" variant="outline" size="sm" icon="sliders" onPress={() => setEditing(true)} />
            )}
          </View>
        }
      />
      <View
        style={{ borderRadius: 28, backgroundColor: editing ? colors.surfaceCanvas : 'transparent', padding: editing ? 24 : 0, minHeight: editing ? 620 : undefined, overflow: 'hidden' }}
      >
        {editing && <GridPattern />}
        <View onLayout={(e) => setGridW(e.nativeEvent.layout.width)} style={{ flexDirection: 'row', flexWrap: 'wrap', gap: GAP, alignItems: 'flex-start' }}>
          {colW > 0 &&
            widgets.map((w) => {
              const def = widgetDef(w.type);
              const C = def.Component;
              return (
                <WidgetFrame
                  key={w.id}
                  width={widthOf(w.span)}
                  editing={editing}
                  onLayoutRect={(r) => rects.current.set(w.id, r)}
                  onDragEnd={(dx, dy) => move(w.id, dx, dy)}
                  onResize={() => resize(w.id)}
                  onRemove={() => onChange(widgets.filter((x) => x.id !== w.id))}
                  canResize={def.spans.length > 1 && cols > 1}
                >
                  <C />
                </WidgetFrame>
              );
            })}
          {editing && colW > 0 && (
            <Hoverable
              onPress={() => setPicker(true)}
              style={{ width: colW, height: 280, borderRadius: 16, borderWidth: 1.5, borderStyle: 'dashed', borderColor: '#D6DAE1', backgroundColor: '#FFF', alignItems: 'center', justifyContent: 'center', gap: 10 }}
              hoverStyle={{ borderColor: colors.blue }}
            >
              <Icon name="plus" size={36} color={colors.blue} strokeWidth={1.4} />
              <T size={18} weight="bold">
                위젯 추가
              </T>
              <T size={13} color={colors.textSub}>
                클릭해서 위젯을 골라보세요
              </T>
            </Hoverable>
          )}
        </View>
      </View>
      <T size={13} color={colors.textSub} style={{ marginTop: 20 }}>
        {editing ? '상단 손잡이로 이동 · 크기 조정으로 너비 변경 · 4열 격자에 맞춰 배치' : '추가한 위젯은 언제든 바꾸거나 삭제할 수 있어요.'}
      </T>
      {picker && <WidgetPicker existing={widgets.map((w) => w.type)} onAdd={add} onClose={() => setPicker(false)} />}
    </Page>
  );
}

function GridPattern() {
  return (
    <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
      <Svg width="100%" height="100%">
        <Defs>
          <Pattern id="grid24" width={24} height={24} patternUnits="userSpaceOnUse">
            <Path d="M24 0H0V24" fill="none" stroke="#E6E9EE" strokeWidth={1} />
          </Pattern>
        </Defs>
        <Rect width="100%" height="100%" fill="url(#grid24)" />
      </Svg>
    </View>
  );
}

/** 편집 중 위젯 테두리 — 손잡이 드래그로 순서 변경, 크기 조정, 삭제 */
function WidgetFrame({
  width,
  editing,
  children,
  onLayoutRect,
  onDragEnd,
  onResize,
  onRemove,
  canResize,
}: {
  width: number;
  editing: boolean;
  children: React.ReactNode;
  onLayoutRect: (r: LayoutRectangle) => void;
  onDragEnd: (dx: number, dy: number) => void;
  onResize: () => void;
  onRemove: () => void;
  canResize: boolean;
}) {
  const [pan] = useState(() => new Animated.ValueXY());
  const [dragging, setDragging] = useState(false);
  const endRef = useRef(onDragEnd);
  useEffect(() => {
    endRef.current = onDragEnd;
  });
  const responder = useMemo(
    () =>
      // eslint-disable-next-line react-hooks/refs -- 핸들러는 렌더 중이 아니라 제스처 이벤트에서만 실행됨
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: () => setDragging(true),
        onPanResponderMove: Animated.event([null, { dx: pan.x, dy: pan.y }], { useNativeDriver: false }),
        onPanResponderRelease: (_e, g) => {
          endRef.current(g.dx, g.dy);
          pan.setValue({ x: 0, y: 0 });
          setDragging(false);
        },
        onPanResponderTerminate: () => {
          pan.setValue({ x: 0, y: 0 });
          setDragging(false);
        },
      }),
    [pan],
  );

  if (!editing)
    return (
      <View style={{ width }} onLayout={(e) => onLayoutRect(e.nativeEvent.layout)}>
        {children}
      </View>
    );

  const handle = (pos: object) => <View style={[{ position: 'absolute', width: 9, height: 9, backgroundColor: '#FFF', borderWidth: 1.5, borderColor: colors.blue, zIndex: 3 }, pos]} />;

  return (
    <Animated.View
      onLayout={(e) => onLayoutRect(e.nativeEvent.layout)}
      style={[
        { width, borderRadius: 16, borderWidth: 1.5, borderColor: colors.blue, backgroundColor: '#FFF', padding: 6, paddingTop: 0, transform: pan.getTranslateTransform() },
        dragging && { zIndex: 100, opacity: 0.92, ...shadow.modal },
      ]}
    >
      {handle({ top: -5, left: -5 })}
      {handle({ top: -5, right: -5 })}
      {handle({ bottom: -5, left: -5 })}
      {handle({ bottom: -5, right: -5 })}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', height: 30, paddingHorizontal: 6 }}>
        <View
          {...responder.panHandlers}
          style={[{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4, paddingRight: 12 }, Platform.OS === 'web' && ({ cursor: dragging ? 'grabbing' : 'grab', userSelect: 'none' } as object)]}
          accessibilityLabel="끌어서 이동"
        >
          <Icon name="grip" size={12} color={colors.textSub} />
          <T size={11} color={colors.textSub} selectable={false}>
            끌어서 이동
          </T>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {canResize && (
            <Hoverable onPress={onResize} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, padding: 4 }} hoverStyle={{ opacity: 0.7 }}>
              <Icon name="external" size={11} color={colors.textSub} />
              <T size={11} color={colors.textSub}>
                크기 조정
              </T>
            </Hoverable>
          )}
          <Hoverable onPress={onRemove} style={{ padding: 4 }} hoverStyle={{ opacity: 0.7 }} accessibilityLabel="위젯 삭제">
            <Icon name="x" size={13} color={colors.textSub} />
          </Hoverable>
        </View>
      </View>
      <View pointerEvents={dragging ? 'none' : 'auto'}>{children}</View>
    </Animated.View>
  );
}

function WidgetPicker({ existing, onAdd, onClose }: { existing: WidgetType[]; onAdd: (t: WidgetType) => void; onClose: () => void }) {
  const { isMobile } = useBreakpoint();
  return (
    <Sheet visible onClose={onClose} width={720}>
      <SheetHeader title="위젯 추가" eyebrow="홈 직접 사용자화" onClose={onClose} />
      {(['기본', '메모'] as const).map((g) => (
        <View key={g} style={{ marginBottom: 20, gap: 10 }}>
          <T size={13} weight="semibold" color={colors.textSub}>
            {g === '기본' ? '기본 위젯' : '메모 위젯'}
          </T>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            {WIDGETS.filter((w) => w.group === g).map((w) => {
              const added = existing.includes(w.type);
              return (
                <Hoverable
                  key={w.type}
                  disabled={added}
                  onPress={() => onAdd(w.type)}
                  style={{ width: isMobile ? '100%' : '48.8%', borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 4, opacity: added ? 0.5 : 1 }}
                  hoverStyle={{ borderColor: colors.blue, backgroundColor: colors.blueSoft }}
                >
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                    <T size={14} weight="semibold">
                      {w.title}
                    </T>
                    <T size={11} color={added ? colors.textMuted : colors.blue}>
                      {added ? '추가됨' : '+ 추가'}
                    </T>
                  </View>
                  <T size={12} color={colors.textSub}>
                    {w.desc}
                  </T>
                </Hoverable>
              );
            })}
          </View>
        </View>
      ))}
    </Sheet>
  );
}
