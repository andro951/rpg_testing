"use strict";

{
    const TokenDefinition = GrammarForge.TokenDefinition;

    GrammarForge.GrammarLexer = class GrammarLexer {
        static grammarTokens = [
            new TokenDefinition("DEFINED_AS", /:(=|:=)?/),
            new TokenDefinition("LPAREN", /\(/),
            new TokenDefinition("RPAREN", /\)/),
            new TokenDefinition("LBRACE", /\{/),
            new TokenDefinition("RBRACE", /\}/),
            new TokenDefinition("COMMENT_HASH", /#.*$/m, 'IGNORE'),
            new TokenDefinition("COMMENT_SLASH", /\/\/.*$/m, 'IGNORE'),
            new TokenDefinition("COMMENT_BLOCK", /\/\*[\s\S]*?\*\//, 'IGNORE'),
            new TokenDefinition("REGEX", /\/(?:\\.|[^\t\r\n\f\v\/])+\/[gimsuy]*/),
            new TokenDefinition("MATH_SYMBOL", /(\|\||&&|==|!=|<=|>=|-#|\+#|[\-\/%!^])/),
            new TokenDefinition("TAG_OPEN", /</),
            new TokenDefinition("TAG_CLOSE", />/),
            new TokenDefinition("ORBAR", /\|/),
            new TokenDefinition("STAR", /\*/),
            new TokenDefinition("PLUS", /\+/),
            new TokenDefinition("ELLIPSIS", /\.\.\./),
            new TokenDefinition("QUESTION", /\?/),
            new TokenDefinition("TOKEN", /[A-Z][A-Z0-9_]*/),
            //new TokenDefinition("STRING", /'(?:\\.|[^'])*'|"(?:\\.|[^"])*"/),
            new TokenDefinition("IDENTIFIER", /[a-zA-Z_][a-zA-Z0-9_]*/),
            new TokenDefinition("INT", /\d+/),
        ]
        
        static lexer = new GrammarForge.Lexer(this.grammarTokens);
        static tokenize = (str) => {
            return GrammarForge.GrammarLexer.lexer.tokenize(str);
        }
    }
}
