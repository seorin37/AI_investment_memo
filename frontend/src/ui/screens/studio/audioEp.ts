import { mockAudioEpisode } from './Studio.mock';
import type { MadeItem } from './Studio.types';

/**
 * 오디오 한 편의 플레이어 내용 (2026-11-24). mock(mockAudioEpisode)과 서버 결과(studio_items.content,
 * backend app/studio_audio/episode.to_content)가 같은 모양: hosts · dur · chapters [[초, 이름]] · script [[초, 'A'|'B', 문장]] ·
 * sources · market_source · memo_link. 서버는 연결된 메모가 없으면 memo_link가 null이다.
 * store(studioPlayer)도 이 파일을 읽으므로 API·react-query를 가져오지 않는다.
 */
export type AudioEp = Omit<typeof mockAudioEpisode, 'memo_link'> & { memo_link: typeof mockAudioEpisode.memo_link | null };

/** 만든 항목의 플레이어 내용. 서버 오디오면 그 내용, 아니면(mock 모드·예시) mock 한 편 */
export const epOf = (m?: MadeItem | null): AudioEp => m?.audio?.ep ?? mockAudioEpisode;
