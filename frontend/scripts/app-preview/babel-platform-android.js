/**
 * 앱 미리보기(웹) 빌드 전용 babel 플러그인 (babel.config.js 가 APP_PREVIEW=1 일 때만 켬).
 * src 화면 코드의 Platform.OS 를 'android' 로, Platform.select({...}) 를 android → native → default 값으로 바꿔
 * 웹 번들에서도 앱 화면 분기를 탄다. 로그인·저장소·API 주소 같은 브라우저 동작 파일(KEEP_WEB)은 건드리지 않는다.
 */
const path = require('node:path');

const SRC = path.join(__dirname, '..', '..', 'src') + path.sep;
const KEEP_WEB = ['config', 'lib', 'api', path.join('store', 'auth.ts'), path.join('store', 'audioEngine.ts')].map((p) =>
  path.join(SRC, p),
);

module.exports = function platformAndroid({ types: t }) {
  const skip = (state) => {
    const f = state.filename || '';
    return !f.startsWith(SRC) || KEEP_WEB.some((p) => f.startsWith(p));
  };
  const isPlatform = (node) => t.isIdentifier(node, { name: 'Platform' });
  return {
    name: 'memos-app-preview-platform',
    visitor: {
      MemberExpression(p, state) {
        if (skip(state)) return;
        const { node } = p;
        if (!isPlatform(node.object) || node.computed || !t.isIdentifier(node.property, { name: 'OS' })) return;
        if (p.parentPath.isAssignmentExpression({ left: node })) return;
        p.replaceWith(t.stringLiteral('android'));
      },
      CallExpression(p, state) {
        if (skip(state)) return;
        const { callee, arguments: args } = p.node;
        if (!t.isMemberExpression(callee) || !isPlatform(callee.object) || !t.isIdentifier(callee.property, { name: 'select' })) return;
        const obj = args[0];
        if (!t.isObjectExpression(obj)) return;
        const find = (k) =>
          obj.properties.find(
            (q) => t.isObjectProperty(q) && !q.computed && ((t.isIdentifier(q.key) && q.key.name === k) || (t.isStringLiteral(q.key) && q.key.value === k)),
          );
        const hit = find('android') ?? find('native') ?? find('default');
        p.replaceWith(hit ? hit.value : t.identifier('undefined'));
      },
    },
  };
};
