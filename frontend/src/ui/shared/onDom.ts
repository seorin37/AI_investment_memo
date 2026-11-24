/** 브라우저에서 그리는 중인지. 앱 미리보기(웹)는 Platform.OS 가 'android' 로 바뀌어 있어 Platform 으로는 알 수 없음 */
export const ON_DOM = typeof document !== 'undefined';
