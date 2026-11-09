const GRAMMAR_FORGE_LIB_VERSION = '2.1.4';
const BASE_URL = 'https://andro951.github.io/GrammarForge/';

const files = [
  'grammarForge/grammarForge.js',
  'grammarForge/token.js',
  'grammarForge/tokenDefinition.js',
  'grammarForge/lexer.js',
  'grammarForge/parser.js',
  'grammarForge/exec.js',
  'grammarForge/tokenStream.js',
  'grammarForge/grammarLexer.js',
  'grammarForge/grammarParser.js',
  'grammarForge/grammarParser/functions.js',
  'grammarForge/grammarParser/expression.js',
  'grammarForge/grammarParser/wordBase.js',
  'grammarForge/grammarParser/word.js',
  'grammarForge/grammarParser/qWord.js',
  'grammarForge/grammarParser/par.js',
  'grammarForge/grammarParser/expList.js',
  'grammarForge/grammarParser/rule.js',
  'grammarForge/grammarParser/term.js',
  'grammarForge/grammarParser/astNode.js',
  'grammarForge/grammarParser/emptyNode.js',
  'grammarForge/grammarParser/expNode.js',
  'grammarForge/grammarParser/tokenNode.js',
  'grammarForge/grammarParser/symbolNode.js',
  'grammarForge/flowControl.js',
  'grammarForge/functionDeclaration.js',
  'grammarForge/programTestCase.js',
  'grammarForge/ruleFunctionDefinition.js',
  'scriptForge/scriptForge.js',
  'scriptForge/script.js',
  'scriptForge/scriptAction.js',
  'scriptForge/scriptTrigger.js',
  'scriptForge/scriptDataGetter.js',
  'scriptForge/scriptTestCase.js',
].map(f => BASE_URL + f + '?v=' + GRAMMAR_FORGE_LIB_VERSION);

(function loadNext(index) {
  if (index >= files.length) {
    const evt = new Event('GrammarForgeLoaded');
    window.dispatchEvent(evt);
    console.log(`GrammarForge ${GRAMMAR_FORGE_LIB_VERSION} fully loaded`);
    return;
  }

  const script = document.createElement('script');
  script.src = files[index];
  script.onload = () => loadNext(index + 1);
  script.onerror = () => {
    console.error('Failed to load GrammarForge script:', files[index]);
  };
  document.head.appendChild(script);
})(0);
