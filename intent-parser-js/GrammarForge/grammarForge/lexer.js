"use strict";

{
    const TokenDefinition = GrammarForge.TokenDefinition;
    const Token = GrammarForge.Token;
    const debuggingLexer = false;

    GrammarForge.Lexer = class Lexer {
        constructor(tokenDefinitions) {
            this.tokenDefinitions = tokenDefinitions;
            this.index = 0;
            this.tokens = [];
            this.tokenDefinitions.push(new TokenDefinition("COMMA", /,/));
            this.tokenDefinitions.push(new TokenDefinition("WHITESPACE", /\s+/, 'IGNORE'));
            this.tokenDefinitions.push(new TokenDefinition("SYMBOL", /[^a-zA-Z0-9_\s:|()*+?'"\`;]/));
            this.tokenDefinitions.push(new TokenDefinition("UNKNOWN", /./));

            Object.freeze(this.tokenDefinitions);

            const tokenSet = new Set();
            for (let tokenDef of this.tokenDefinitions) {
                if (tokenSet.has(tokenDef.type))
                    throw new Error(`Duplicate token type: ${tokenDef.type}`);

                tokenSet.add(tokenDef.type);
            }
        }

        tokenize = (str) => {
            if (debuggingLexer) {
                console.log("Starting tokenization...");
                console.log(`string:\n${str}\n`);
            }
            
            this.str = str;
            this.tokens = [];
            this.index = 0;
            while (this.index < this.str.length) {
                let token = this.getNextToken();
                if (!token)
                    continue;

                if (token.type === "UNKNOWN")
                    throw new Error(`Unexpected character: ${token.value} at index ${this.index}`);

                this.tokens.push(token);
            }

            if (debuggingLexer) {
                for (let i = 0; i < this.tokens.length; i++) {
                    const token = this.tokens[i];
                    console.log(`${i}: ${token.type} (${token.value})`);
                }
            }

            return this.tokens;
        }

        getNextToken = () => {
            const substring = this.str.slice(this.index);
            for (let tokenDef of this.tokenDefinitions) {
                const match = substring.match(tokenDef.regex);
                if (match && match.index === 0) {
                    const value = match[0];
                    this.index += value.length;
                    if (tokenDef.tag === 'IGNORE')
                        return null;

                    return new Token(tokenDef.type, value);
                }
            }

            throw new Error(`Unexpected character: ${this.str[this.index]} at index ${this.index}`);
        }
    }
}
