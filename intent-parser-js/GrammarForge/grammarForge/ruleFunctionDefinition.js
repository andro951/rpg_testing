"use strict";

GrammarForge.RuleFunctionDefinition = class RuleFunctionDefinition {
    constructor(ruleName, expressionString, func) {
        if (typeof ruleName !== 'string' || typeof expressionString !== 'string')
            throw new Error('ruleName and expressionString must be strings.');
        
        if (func !== null && typeof func !== 'function')
            throw new Error('func must be a function or null.');

        this.ruleName = ruleName;
        this.expressionString = expressionString;
        this.func = func;
    }
}
