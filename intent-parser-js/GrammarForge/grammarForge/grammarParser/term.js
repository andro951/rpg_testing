"use strict";

GrammarForge.Term = class Term extends GrammarForge.Word {
    constructor(token) {
        super();
        this.type = token.type;
        this.value = token.value;
        this.string = this.toString();
    }

    //Returns true if left recursion was checked and not found
    //Throws an error if left recursion is found
    //Returns false if this word was not a match, but is optional
    checkWordForLeftRecursion = (parser, expr, lookAheadSet) => {
        if (this.type === "IDENTIFIER") {
            const rule = parser.getRule(this.value);
            if (!rule)
                throw new Error(`No rule found for identifier ${this.value} in expression: ${expr.expressionString}`);

            return rule.checkLeftRecursion(parser, lookAheadSet);
        }
        else if (lookAheadSet) {
            lookAheadSet.add(this.value);
        }
        
        return true;//Found and checked the first non-optional word
    }

    getParseFunc = (parser) => {
        let funcIndex = parser.ruleSubFunctionLookup.get(this.string);
        if (funcIndex === undefined) {
            let func;
            const type = this.type;
            switch (this.type) {
                case "IDENTIFIER":
                    const rule = parser.getRule(this.value);
                    if (!rule)
                        throw new Error(`No rule found for identifier ${this.value}`);

                    func = (tokenStream) => {
                        return parser.ruleFunctions[rule.index](tokenStream);
                    };
                    break;
                case "TOKEN":
                    const tokenType = this.value;
                    func = (tokenStream) => {
                        return parser.token(tokenStream, tokenType);
                    };
                    break;
                case "SYMBOL":
                    const symbol = this.value;
                    func = (tokenStream) => {
                        return parser.symbol(tokenStream, symbol);
                    };
                    break;
                default:
                    throw new Error(`getSingleWordParseFunc: ${this.type} not supported`);
            }

            funcIndex = parser.addSubFunction(this.string, func);
        }
        
        return parser.ruleSubFunctions[funcIndex];
    }

    getTryParseFunc = (parser) => {
        let funcIndex = parser.ruleTrySubFunctionLookup.get(this.string);
        if (funcIndex === undefined) {
            let func;
            const type = this.type;
            switch (this.type) {
                case "IDENTIFIER":
                    const rule = parser.getRule(this.value);
                    if (!rule)
                        throw new Error(`No rule found for identifier ${this.value}`);

                    func = (tokenStream) => {
                        const tryResult = parser.ruleTryFunctions[rule.index](tokenStream);
                        if (!tryResult)
                            return null;

                        return tryResult;
                    };
                    break;
                case "TOKEN":
                    const tokenType = this.value;
                    func = (tokenStream) => {
                        const tryResult = parser.try_token(tokenStream, tokenType);
                        if (!tryResult)
                            return null;

                        return tryResult;
                    };
                    break;
                case "SYMBOL":
                    const symbol = this.value;
                    func = (tokenStream) => {
                        const tryResult = parser.try_symbol(tokenStream, symbol);
                        if (!tryResult)
                            return null;

                        return tryResult;
                    };
                    break;
                default:
                    throw new Error(`getSingleWordParseFunc: ${this.type} not supported`);
            }

            funcIndex = parser.addTrySubFunction(this.string, func);
        }

        return parser.ruleTrySubFunctions[funcIndex];
    }

    setKeptWordIndexs = (parser) => {
        if (this.hasKeptWords)
            return 1;

        let count = 0;
        switch (this.type) {
            case "IDENTIFIER":
                const rule = parser.getRule(this.value);
                if (!rule)
                    throw new Error(`No rule found for identifier ${this.value}`);

                count = rule.setKeptWordIndexs(parser);
                break;
            case "TOKEN":
                if (parser.parseTokenFunctions.get(this.value) || parser.tokenTags.get(this.value) === "KEEP")
                    count = 1;

                break;
        }

        if (count > 0)
            this.hasKeptWords = true;

        return count;
    }

    getKeptWordsFromIndexs = (_) => {
        if (this.hasKeptWords)
            return [ this ];

        return [];
    }

    getChildren = (parser, childrenIndexSet) => {
        if (this.type === "IDENTIFIER") {
            const rule = parser.getRule(this.value);
            if (!rule)
                throw new Error(`No rule found for non-terminal: ${this.value}`);

            if (childrenIndexSet.has(rule.index))
                return;
            
            childrenIndexSet.add(rule.index);
            rule.getChildren(parser, childrenIndexSet);
        }
    }

    // walk = function*() {
    //     yield this;
    // }

    toString() {
        return `${this.value}`;
        //return `${this.value}{${this.type}}`;
    }
}
