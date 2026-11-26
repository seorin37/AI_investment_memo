/**
 * 기본 Expo babel 설정 그대로. APP_PREVIEW=1 (웹 /app 앱 미리보기 빌드)일 때만 Platform 을 'android' 로 바꾸는 플러그인을 더한다.
 * babel-preset-expo 는 expo 패키지 안에 설치돼 있어서 expo 기준으로 찾는다.
 */
const path = require('node:path');

const expoPreset = require.resolve('babel-preset-expo', { paths: [path.dirname(require.resolve('expo/package.json'))] });

module.exports = function (api) {
  const preview = process.env.APP_PREVIEW === '1';
  api.cache.using(() => preview);
  return {
    presets: [expoPreset],
    plugins: preview ? [require('./scripts/app-preview/babel-platform-android')] : [],
  };
};
