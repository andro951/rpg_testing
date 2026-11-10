"use strict";

{
    GrammarForge.Parser = class Parser {
        constructor(rules, lexer) {
            this.rules = rules;
            this.lexer = lexer;
            this.tokens = [];
            this.parseTokenFunctions = new Map();
            this.tokensWithParseFunctions = new Set();
            this.partialAstBeingParsed = null;
            this.populateDefaultParseTokenFunctions();
            this.checkDuplicateRuleNames();
            this.tokenTags = new Map();
            for (let tokenDef of this.lexer.tokenDefinitions) {
                this.tokenTags.set(tokenDef.type, tokenDef.tag);
            }

            this.createRuleMaps();

            for (const rule of this.rules) {
                for (const expression of rule.expList.expressions) {
                    expression.setKeptWordIndexs(this);
                }
            }

            for (const rule of this.rules) {
                rule.checkLeftRecursion(this);
            }
            
            this.createRuleParseFunctions();
        }

        checkDuplicateRuleNames = () => {
            const ruleNames = new Set();
            for (const rule of this.rules) {
                if (ruleNames.has(rule.name))
                    throw new Error(`Duplicate rule name: ${rule.name}`);

                ruleNames.add(rule.name);
            }
        }

        createRuleMaps = () => {
            this.ruleIndexLookup = new Map();//Map<ruleName, ruleIndex>; ruleIndexLookup.get(ruleName) => ruleIndex
            for (let i = 0; i < this.rules.length; i++) {
                const rule = this.rules[i];
                this.ruleIndexLookup.set(rule.name, i);
            }

            Object.freeze(this.ruleIndexLookup);

            this.ruleTagLookup = new Map();
            for (let i = 0; i < this.rules.length; i++) {
                const rule = this.rules[i];
                if (rule.tag !== null) {
                    if (this.ruleTagLookup.has(rule.tag))
                        throw new Error(`Duplicate tag found, tag: ${rule.tag} on rules ${this.ruleTagLookup.get(rule.tag).name} and ${rule.name}`);

                    this.ruleTagLookup.set(rule.tag, rule);
                }
            }

            this.metaExpressionLookup = new Map();
            for (let i = 0; i < this.rules.length; i++) {
                const rule = this.rules[i];
                for (let j = 0; j < rule.expList.expressions.length; j++) {
                    const expression = rule.expList.expressions[j];
                    const tag = expression.tag;
                    if (tag !== null) {
                        if (!this.metaExpressionLookup.has(tag))
                            this.metaExpressionLookup.set(tag, []);

                        this.metaExpressionLookup.get(tag).push([rule, expression]);
                    }
                }
            }

            Object.freeze(this.metaExpressionLookup);

            const expRule = this.ruleTagLookup.get("exp");
            if (expRule) {
                const expRules = new Set([expRule.index]);
                expRule.getChildren(this, expRules);
                for (const ruleIndex of expRules) {
                    this.rules[ruleIndex].isExpRule = true;
                }
            }
        }

        getRule = (ruleName) => {
            const ruleIndex = this.ruleIndexLookup.get(ruleName);
            if (ruleIndex === undefined)
                throw new Error(`No rule found with name: ${ruleName}`);

            return this.rules[ruleIndex];
        }

        createRuleParseFunctions = () => {
            this.ruleFunctions = Array(this.rules.length).fill(null);
            this.ruleTryFunctions = Array(this.rules.length).fill(null);
            this.ruleSubFunctions = [];
            this.ruleSubFunctionKeys = [];
            this.ruleSubFunctionLookup = new Map();//Needs to stay as Map<expressionString, subFunctionIndex> because expressions can be either an indexed expression of a rule, or an indexed expression inside parentheses inside another expression.
            this.ruleTrySubFunctions = [];
            this.ruleTrySubFunctionKeys = [];
            this.ruleTrySubFunctionLookup = new Map();//Needs to stay as Map<expressionString, subFunctionIndex> because expressions can be either an indexed expression of a rule, or an indexed expression inside parentheses inside another expression.
            for (const rule of this.rules) {
                rule.createParseFunctions(this);
            }
        }

        addSubFunction = (funcKey, func) => {
            if (this.ruleSubFunctionLookup.has(funcKey))
                throw new Error(`Sub function with key ${funcKey} already exists.`);

            if (!funcKey)
                throw new Error("Function key is required to add sub function.");
            
            const index = this.ruleSubFunctions.length;
            this.ruleSubFunctions.push(func.bind(this));
            this.ruleSubFunctionKeys.push(funcKey);
            this.ruleSubFunctionLookup.set(funcKey, index);
            return index;
        }

        addTrySubFunction = (funcKey, func) => {
            if (this.ruleTrySubFunctionLookup.has(funcKey))
                throw new Error(`Try sub function with key ${funcKey} already exists.`);

            if (!funcKey)
                throw new Error("Function key is required to add try sub function.");

            const index = this.ruleTrySubFunctions.length;
            this.ruleTrySubFunctions.push(func.bind(this));
            this.ruleTrySubFunctionKeys.push(funcKey);
            this.ruleTrySubFunctionLookup.set(funcKey, index);
            return index;
        }

        parse = (str) => {
            this.partialAstBeingParsed = null;

            this.tokens = this.lexer.tokenize(str);
            return this.parseTokens(this.tokens);
        }

        parseTokens = (tokens) => {
            this.partialAstBeingParsed = null;

            this.tokens = tokens;
            this.tokenStream = new GrammarForge.TokenStream(this.tokens);
            const ast = this.ruleFunctions[0](this.tokenStream);
            if (!this.tokenStream.end()) {
                this.partialAstBeingParsed = ast;
                throw new Error("Unexpected tokens at end of input.");
            }
            
            return ast;
        }

        token = (tokenStream, tokenType) => {
            const token = tokenStream.currentToken();
            if (token.type !== tokenType)
                throw new Error(`Expected ${tokenType} token, found ${tokenStream.currentToken().type}`);

            tokenStream.match(tokenType);
            return this.tokenToAST(token);
        }

        try_token = (tokenStream, tokenType) => {
            const token = tokenStream.tryCurrentToken();
            if (!token)
                return null;
            
            if (!tokenStream.tryMatch(tokenType))
                return null;

            return this.tokenToAST(token);
        }

        _tryGetDefaultParseTokenFunction = (tokenTag) => {
            switch (tokenTag) {
                case 'int':
                    return (token) => {
                        const value = parseInt(token.value);
                        if (value > Number.MAX_SAFE_INTEGER || value < Number.MIN_SAFE_INTEGER)
                            throw new Error(`Integer value ${token.value} is out of safe integer range.`);

                        if (!isFinite(value))
                            throw new Error(`Invalid integer value: ${token.value}`);

                        return value;
                    };
                case 'float':
                    return (token) => {
                        const value = parseFloat(token.value);
                        if (!isFinite(value))
                            throw new Error(`Invalid float value: ${token.value}`);

                        return value;
                    };
                case 'bool':
                    return (token) => token.value === 'true';
                case 'string':
                    return (token) => {
                        const s = token.value.substring(1, token.value.length - 1);
                        return s;
                    };
                default:
                    return null;
            }
        }

        populateDefaultParseTokenFunctions = () => {
            for (const tokenDef of this.lexer.tokenDefinitions) {
                const type = tokenDef.type;
                if (this.parseTokenFunctions.has(type))
                    continue;

                const tag = tokenDef.tag;
                if (tag !== null) {
                    const func = this._tryGetDefaultParseTokenFunction(tag);
                    if (func) {
                        this.setParseTokenFunction(type, func);
                    }
                }
            }
        }

        setParseTokenFunction = (type, func) => {
            this.parseTokenFunctions.set(type, func);
            this.tokensWithParseFunctions.add(type);
        }

        tokenToAST = (token) => {
            const parseFunction = this.parseTokenFunctions.get(token.type);
            const value = parseFunction ? parseFunction(token) : token.value;
            return new GrammarForge.TokenNode(token.type, value);
        }

        symbol = (tokenStream, symbol) => {
            const token = tokenStream.currentToken();
            if (token.type !== 'SYMBOL')
                throw new Error(`Expected SYMBOL token '${symbol}', found ${tokenStream.currentToken().type}`);

            if (token.value !== symbol)
                throw new Error(`Expected symbol '${symbol}', found '${token.value}'`);

            tokenStream.match('SYMBOL');

            return new GrammarForge.SymbolNode(symbol);
            return [`SYMBOL`, token.value];
        }

        try_symbol = (tokenStream, symbol) => {
            const token = tokenStream.tryCurrentToken();
            if (!token)
                return null;

            if (token.type !== 'SYMBOL')
                return null;

            if (token.value !== symbol)
                return null;

            if (!tokenStream.tryMatch('SYMBOL'))
                return null;

            return new GrammarForge.SymbolNode(symbol);
            return [`SYMBOL`, token.value];
        }
    }
}
