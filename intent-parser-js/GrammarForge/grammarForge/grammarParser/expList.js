"use strict";

GrammarForge.ExpList = class ExpList extends GrammarForge.Word {
    constructor(expressions) {
        super();
        if (!Array.isArray(expressions) || expressions.length === 0)
            throw new Error("expressions must be a non-empty array");

        this.expressions = expressions;
        this.expListString = this.toString();
        this.subFuncString = this.expListString + `$EL`;
    }

    _getResult = (result) => {
        if (GrammarForge.makeFullAST) {
            return [ 'EXPLIST', result ];
        }
        else {
            return result;
        }
    }

    getParseFunc = (parser) => {
        let funcIndex = parser.ruleSubFunctionLookup.get(this.subFuncString);
        if (funcIndex === undefined) {
            let func;
            switch (this.expressions.length) {
                case 0:
                    throw new Error(`ExpList has no expressions.`);
                case 1:
                    const expression = this.expressions[0];
                    const expressionParse = expression.getParseFunc(parser);
                    const expressionString = expression.expressionString;
                    func = (tokenStream) => {
                        const expressionResult = expressionParse(tokenStream);
                        return this._getResult(expressionResult);
                    }
                    break;
                default:
                    const expressionTryParseFuncs = [];
                    const expressionStrings = [];
                    const expressionLookaheadSets = [];
                    for (let i = 0; i < this.expressions.length; i++) {
                        expressionTryParseFuncs.push(this.expressions[i].getTryParseFunc(parser));
                        expressionStrings.push(this.expressions[i].expressionString);
                        expressionLookaheadSets.push(this.expressions[i].getLookaheadSet(parser));
                    }

                    func = (tokenStream) => {
                        const token = tokenStream.tryCurrentToken();
                        if (token === null)
                            return new GrammarForge.EmptyNode();//Fall back for an empty program.

                        for (let i = 0; i < this.expressions.length; i++) {
                            if (token.type === 'SYMBOL') {
                                if (!expressionLookaheadSets[i].has(token.value))
                                    continue;
                            }
                            else {
                                if (!expressionLookaheadSets[i].has(token.type))
                                    continue;
                            }

                            const tryParseResult = expressionTryParseFuncs[i](tokenStream);
                            if (tryParseResult) {
                                return this._getResult(tryParseResult);
                            }
                        }

                        throw new Error(`No expressions parsed successfully for ExpList with multiple expressions.`);
                    }
                    break;
            }

            funcIndex = parser.addSubFunction(this.subFuncString, func);
        }

        return parser.ruleSubFunctions[funcIndex];
    }

    getTryParseFunc = (parser) => {
        let funcIndex = parser.ruleTrySubFunctionLookup.get(this.subFuncString);
        if (funcIndex === undefined) {
            let tryFunc;
            switch (this.expressions.length) {
                case 0:
                    throw new Error(`ExpList has no expressions.`);
                case 1:
                    const expression = this.expressions[0];
                    const expressionString = expression.expressionString;
                    const expressionTryParse = expression.getTryParseFunc(parser);

                    tryFunc = (tokenStream) => {
                        const tryParseResult = expressionTryParse(tokenStream);
                        if (!tryParseResult)
                            return null;
                        
                        return this._getResult(tryParseResult);
                    }
                    break;
                default:
                    const expressionTryParseFuncs = [];
                    const expressionStrings = [];
                    const expressionLookaheadSets = [];
                    for (let i = 0; i < this.expressions.length; i++) {
                        expressionTryParseFuncs.push(this.expressions[i].getTryParseFunc(parser));
                        expressionStrings.push(this.expressions[i].expressionString);
                        expressionLookaheadSets.push(this.expressions[i].getLookaheadSet(parser));
                    }

                    tryFunc = (tokenStream) => {
                        const token = tokenStream.tryCurrentToken();
                        if (token === null)
                            return null;
                        
                        for (let i = 0; i < this.expressions.length; i++) {
                            if (token.type === 'SYMBOL') {
                                if (!expressionLookaheadSets[i].has(token.value))
                                    continue;
                            }
                            else {
                                if (!expressionLookaheadSets[i].has(token.type))
                                    continue;
                            }

                            const tryParseResult = expressionTryParseFuncs[i](tokenStream);
                            if (tryParseResult) {
                                return this._getResult(tryParseResult);
                            }
                        }

                        return null;
                    }
                    break;
            }

            funcIndex = parser.addTrySubFunction(this.subFuncString, tryFunc);
        }
        
        return parser.ruleTrySubFunctions[funcIndex];
    }

    setKeptWordIndexs = (parser) => {
        const firstExpression = this.expressions[0];
        const firstExpressionKeptWordIndexesCount = firstExpression.setKeptWordIndexs(parser);

        if (this.expressions.length === 1)
            return firstExpressionKeptWordIndexesCount;

        const hasRule = !!firstExpression.rule;
        let anyHasKeptWords = firstExpressionKeptWordIndexesCount > 0;
        for (let i = 1; i < this.expressions.length; i++) {
            const expression = this.expressions[i];
            const expressionKeptWordIndexesCount = expression.setKeptWordIndexs(parser);
            if (hasRule) {
                const expressionHasKeptWords = expressionKeptWordIndexesCount > 0;
                anyHasKeptWords ||= expressionHasKeptWords;

                continue;
            }

            if (expressionKeptWordIndexesCount !== firstExpressionKeptWordIndexesCount)
                throw new Error(`All expressions in an ExpList must have the same number of kept words.  Expression 0 has ${firstExpressionKeptWordIndexesCount} kept words but expression ${i} has ${expressionKeptWordIndexesCount} kept words.`);
        }

        if (hasRule) {
            return anyHasKeptWords ? 1 : 0;
        }

        const firstExpressionKeptWords = firstExpression.getKeptWordsFromIndexs();
        for (const keptWord of firstExpressionKeptWords) {
            if (keptWord.value === undefined)
                throw new Error(`Non-terminal in expression ${firstExpression.expressionString} has no value.`);
        }
        
        for (let i = 0; i < firstExpression.words.length; i++) {
            const word1 = firstExpression.words[i];
            for (let j = 1; j < this.expressions.length; j++) {
                const expression = this.expressions[j];
                const word2 = expression.words[i];
                if (word1.type !== word2.type)
                    throw new Error(`All expressions in an ExpList must have the same types of words in the same order.  Expression 0 word ${i} is type ${word1.type} but expression ${j} word ${i} is type ${word2.type}.`);

                if (word1.type === "IDENTIFIER") {
                    if (word1.value !== word2.value)
                        throw new Error(`All expressions in an ExpList must have the same non-terminals in the same order.  Expression 0 word ${i} is non-terminal ${word1.value} but expression ${j} word ${i} is non-terminal ${word2.value}.`);
                }
            }
        }

        return firstExpressionKeptWordIndexesCount;
    }

    getKeptWordsFromIndexs = (oTypes = null) => {
        const firstExpression = this.expressions[0];
        const firstExpressionKeptWords = firstExpression.getKeptWordsFromIndexs(oTypes);
        return firstExpressionKeptWords;
    }

    getChildren = (parser, childrenIndexSet) => {
        for (let i = 0; i < this.expressions.length; i++) {
            const expr = this.expressions[i];
            expr.getChildren(parser, childrenIndexSet);
        }
    }
    
    // walk = function*() {
    //     yield this.expressions;
    // }

    toString(useNewlines = false) {
        return `${this.expressions.map(expr => expr.toString()).join(useNewlines ? "\n| " : " | ")}`;
    }
}
