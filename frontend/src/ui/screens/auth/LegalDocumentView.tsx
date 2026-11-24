import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/AppText';
import { fpx, ft } from '@/ui/theme';

type Block =
  | { kind: 'h3'; text: string }
  | { kind: 'h4'; text: string }
  | { kind: 'p'; text: string }
  | { kind: 'list'; items: string[] }
  | { kind: 'table'; rows: string[][] };

function plain(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '“')
    .replace(/&#39;/g, '’')
    .trim();
}

function blocksOf(html: string): Block[] {
  const blocks: Block[] = [];
  const re = /<(h3|h4|p|ol|table)[^>]*>([\s\S]*?)<\/\1>/gi;
  let match: RegExpExecArray | null;
  while ((match = re.exec(html))) {
    const tag = match[1].toLowerCase();
    const body = match[2];
    if (tag === 'table') {
      const rows: string[][] = [];
      const rowRe = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
      let row: RegExpExecArray | null;
      while ((row = rowRe.exec(body))) {
        const cells: string[] = [];
        const cellRe = /<(?:th|td)[^>]*>([\s\S]*?)<\/(?:th|td)>/gi;
        let cell: RegExpExecArray | null;
        while ((cell = cellRe.exec(row[1]))) cells.push(plain(cell[1]));
        if (cells.length) rows.push(cells);
      }
      if (rows.length) blocks.push({ kind: 'table', rows });
    } else if (tag === 'ol') {
      const items = Array.from(body.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/gi), (x) => plain(x[1]));
      if (items.length) blocks.push({ kind: 'list', items });
    } else {
      const text = plain(body);
      if (text) blocks.push({ kind: tag as 'h3' | 'h4' | 'p', text });
    }
  }
  return blocks;
}

function MarkedText({ text, style }: { text: string; style: object }) {
  const parts = text.split(/(\[[^\]]+\])/g);
  return (
    <Text style={style}>
      {parts.map((part, i) => /^\[[^\]]+\]$/.test(part) ? <Text key={i} style={st.placeholder}>{part}</Text> : part)}
    </Text>
  );
}

export function LegalDocumentView({ html, variant }: { html: string; variant: 'app' | 'web' }) {
  const blocks = useMemo(() => blocksOf(html), [html]);
  const app = variant === 'app';
  return (
    <ScrollView showsVerticalScrollIndicator={false} style={st.flex} contentContainerStyle={app ? st.appContent : st.webContent}>
      {blocks.map((block, i) => {
        if (block.kind === 'h3') return <MarkedText key={i} text={block.text} style={app ? st.appH3 : st.webH3} />;
        if (block.kind === 'h4') return <MarkedText key={i} text={block.text} style={app ? st.appH4 : st.webH4} />;
        if (block.kind === 'p') return <MarkedText key={i} text={block.text} style={app ? st.appP : st.webP} />;
        if (block.kind === 'list') {
          return <View key={i} style={st.list}>{block.items.map((item, n) => <MarkedText key={n} text={`${n + 1}. ${item}`} style={app ? st.appP : st.webP} />)}</View>;
        }
        return (
          <View key={i} style={[st.table, app ? st.appTable : st.webTable]}>
            {block.rows.map((row, ri) => (
              <View key={ri} style={[st.tableRow, ri > 0 && st.rowLine, ri === 0 && st.tableHead]}>
                {row.map((cell, ci) => (
                  <View key={ci} style={[st.tableCell, ci > 0 && st.cellLine, { flex: ci === 0 ? 0.42 : 0.58 }]}>
                    <MarkedText text={cell} style={[app ? st.appCell : st.webCell, ri === 0 && st.cellHead]} />
                  </View>
                ))}
              </View>
            ))}
          </View>
        );
      })}
    </ScrollView>
  );
}

const st = StyleSheet.create({
  flex: { flex: 1 },
  appContent: { paddingHorizontal: 22, paddingTop: 18, paddingBottom: 120 },
  webContent: { paddingRight: 8, paddingBottom: 20 },
  appH3: { ...ft(16, 1.5), marginTop: 20, marginBottom: 8, color: '#24262A', fontWeight: '700' },
  appH4: { ...ft(15, 1.5), marginTop: 14, marginBottom: 6, color: '#33363B', fontWeight: '700' },
  appP: { ...ft(14, 1.75), marginBottom: 8, color: '#575B63' },
  webH3: { ...fpx(15, 23), marginTop: 18, marginBottom: 8, color: '#24262A', fontWeight: '700' },
  webH4: { ...fpx(14, 21), marginTop: 13, marginBottom: 6, color: '#33363B', fontWeight: '700' },
  webP: { ...fpx(14, 23), marginBottom: 8, color: '#575B63' },
  list: { marginBottom: 8, gap: 3 },
  placeholder: { color: '#A8740A', backgroundColor: '#FFF1C9' },
  table: { overflow: 'hidden', borderWidth: 1, borderColor: '#DDE1E7', marginBottom: 16 },
  appTable: { borderRadius: 12 },
  webTable: { borderRadius: 0 },
  tableRow: { flexDirection: 'row', backgroundColor: '#FFFFFF' },
  tableHead: { backgroundColor: '#F4F5F7' },
  rowLine: { borderTopWidth: 1, borderTopColor: '#DDE1E7' },
  tableCell: { minHeight: 38, justifyContent: 'center', paddingHorizontal: 10, paddingVertical: 8 },
  cellLine: { borderLeftWidth: 1, borderLeftColor: '#DDE1E7' },
  appCell: { ...ft(13, 1.55), color: '#575B63' },
  webCell: { ...fpx(13, 20), color: '#575B63' },
  cellHead: { color: '#33363B', fontWeight: '700' },
});
