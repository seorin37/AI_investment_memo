/**
 * 메모 저장이 서버에서 끝나기 전에 AI 연결(분석)이 먼저 가는 것을 막는다 (2026-11-25).
 * 메모 창에서 글을 고친 뒤 바로 AI 연결을 켜면 서버가 고치기 전 글로 분석해 '추적할 항목을 찾지 못했어요'가 났다.
 * 저장은 trackSave 로 감싸 두고, AI 켜기 직전에 waitSave 로 그 메모의 저장이 끝나기를 기다린다.
 */
const pending = new Map<string, Promise<unknown>>();

export function trackSave<T>(id: string, p: Promise<T>): Promise<T | undefined> {
  const safe = p.catch(() => undefined);
  pending.set(id, safe);
  void safe.finally(() => {
    if (pending.get(id) === safe) pending.delete(id);
  });
  return safe;
}

export function waitSave(id: string | null | undefined): Promise<unknown> {
  return (id && pending.get(id)) || Promise.resolve();
}
