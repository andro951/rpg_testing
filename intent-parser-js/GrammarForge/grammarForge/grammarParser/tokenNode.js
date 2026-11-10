"use strict";

GrammarForge.TokenNode = class TokenNode extends GrammarForge.AstNode {
    constructor(type, value) {
        super();
        this.type = type;
        this.value = value;
    }
    exec() {
        return this.value;
    }
    toString() {
        return `TOKEN: ${this.type}(${this.value})`;
    }
}
