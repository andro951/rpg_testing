"use strict";

GrammarForge.ExpNode = class ExpNode extends GrammarForge.AstNode {
    constructor(expression, nodes) {
        super();
        this.expression = expression;
        this.nodes = nodes;
    }
    exec() {
        return this.expression.execFunc(this.nodes);
    }
    toString() {
        return `EXP (${this.expression.expressionString}): ${this.nodes}`;
    }
}
