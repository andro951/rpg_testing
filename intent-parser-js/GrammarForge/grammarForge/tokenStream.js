"use strict";

GrammarForge.TokenStream = class TokenStream {
    constructor(tokens) {
        this.tokens = tokens;
        if (!Object.isFrozen(this.tokens))
            Object.freeze(this.tokens);

        this.index = 0;
    }

    tryCurrentToken() {
        if (this.index >= this.tokens.length)
            return null;

        return this.tokens[this.index];
    }

    currentToken() {
        this.check(1);
        return this.tokens[this.index];
    }

    increment() {
        this.index++;
    }

    tryMatch(type) {
        if (this.index >= this.tokens.length)
            return false;

        const token = this.tokens[this.index];
        if (token.type === type) {
            this.index++;
            return true;
        }

        return false;
    }

    match(type) {
        this.check(1);
        const token = this.tokens[this.index];
        if (token.type === type) {
            this.index++;
        }
        else {
            throw new Error(`Expected token type ${type}, found ${token.type}`);
        }
    }

    check(size) {
        if (this.index + size <= this.tokens.length)
            return;

        throw new Error(`Not enough tokens in stream. Requested ${size}, but only ${this.tokens.length - this.index} remaining.`);
    }

    end() {
        return this.index >= this.tokens.length;
    }

    clone() {
        const cloned = new GrammarForge.TokenStream(this.tokens);
        cloned.index = this.index;
        return cloned;
    }
}
