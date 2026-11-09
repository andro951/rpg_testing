"use strict";

GrammarForge.SymbolNode = class SymbolNode extends GrammarForge.AstNode {
    constructor(symbol) {
        super();
        this.symbol = symbol;
    }
    exec() {
        return this.symbol;
    }
    toString() {
        return `SYMBOL: ${this.symbol}`;
    }
}
