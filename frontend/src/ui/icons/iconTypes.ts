/** 원본 SVG 를 옮긴 노드: [태그, 속성, 자식] (속성 이름은 react-native-svg 의 camelCase) */
export type IconAttrs = Record<string, string | number>;
export type IconNode = readonly [string, IconAttrs] | readonly [string, IconAttrs, readonly IconNode[]];

export interface IconDef {
  /** 원본 viewBox */
  vb: string;
  /** 원본 width · height */
  w: number;
  h: number;
  /** 가장 많이 쓴 칠 색 — color 를 주면 이 색(과 currentColor)만 바뀜 */
  main: string;
  nodes: readonly IconNode[];
}
