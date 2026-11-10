"use strict";

GrammarForge.EmptyNode = class EmptyNode extends GrammarForge.AstNode {
    constructor() {
        super();
        this.empty = true;
    }
    exec() {
        throw new Error("Cannot execute an empty node.");
    }
    toString() {
        return "EMPTY";
    }
}
