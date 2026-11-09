"use strict";

GrammarForge.AstNode = class AstNode {
    constructor() {
        if (new.target === GrammarForge.AstNode) {
            throw new TypeError("Cannot construct AstNode instances directly");
        }
    }
    exec() {
        throw new Error("Exec not implemented for AstNode base class");
    }
    toString() {
        throw new Error("toString not implemented for AstNode base class");
    }
}
