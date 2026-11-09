"use strict";

GrammarForge.Expression = class Expression {
    constructor(words, index, expressionIndex, metadata = []) {
        if (!words)
            throw new Error("words is required");

        if (!Array.isArray(words))
            throw new Error("words must be an array");

        if (!Array.isArray(metadata))
            throw new Error("metadata must be an array");

        this.words = words;
        this.index = index;
        this.expressionIndex = expressionIndex;
        this.metadata = metadata;
        this.rule = null;//Set in GrammarForge.GrammarParser
        this.tag = this.metadata.length > 0 ? this.metadata[0] : null;
        this.expressionString = this.toString();
        this.execFunc = null;
        this.automaticallyGeneratedFunc = true;
        this.subFuncString = this.expressionString + `$E`;
        Object.freeze(this.words);
    }

    checkMetadata = (rule) => {
        if (this.metadata.length === 0)
            return;

        const tag = this.metadata[0];
        if (this.tag !== tag)
            throw new Error(`Expression tag mismatch.  Expected: ${this.tag}, found: ${tag} in expression: ${this.expressionString}`);

        if (GrammarForge.Expression.tags.has(tag))
            return;

        if (this.metadata.length > 1) {
            if (GrammarForge.Rule.tags.has(tag)) {
                throw new Error(`${tag} is a rule tag, but was on an expression with additional metadata: ${this.metadata.join(" ")}.  Either remove the extra metadata or move the tag to the rule level.`);
            }
            else {
                throw new Error(`Unknown expression tag: ${tag}`);
            }
        }

        if (rule.expressions.length > 1) {
            let allMatch = true;
            for (let i = 0; i < rule.expressions.length; i++) {
                const expr = rule.expressions[i];
                if (expr === this)
                    continue;

                if (expr.metadata.length !== 1 || expr.metadata[0] !== tag) {
                    allMatch = false;
                    break;
                }
            }

            if (allMatch) {
                rule.tag = tag;
                for (let i = 0; i < rule.expressions.length; i++) {
                    const expr = rule.expressions[i];
                    expr.metadata = [];
                    expr.tag = null;
                }

                return;
            }
            else {
                throw new Error(`${tag} is a rule tag, but was put on an expression: ${this.expressionString}, but the rule (${rule.name}) has multiple expressions and not all expressions have the same tag.  Either remove the expression tag or move it to the rule level.`);
            }
        }

        if (rule.tag !== null)
            throw new Error(`${tag} is a rule tag, but the rule already has a tag: ${rule.tag}.  A rule can't have multiple tags.  Either remove the expression tag or move it to the rule level.`);

        rule.tag = tag;
        this.metadata = [];
        this.tag = null;
    }

    getLookaheadSet = (parser) => {
        this.checkWordsForLeftRecursion(parser, null, this.rule === null);
        if (!this.lookAheadSet)
            throw new Error("Lookahead set should have been computed in checkWordsForLeftRecursion.");

        return this.lookAheadSet;
    }

    checkWordsForLeftRecursion = (parser, lookAheadSet) => {
        if (this.lookAheadSet) {
            if (lookAheadSet !== null) {
                for (const token of this.lookAheadSet) {
                    lookAheadSet.add(token);
                }
            }
            
            return true;
        }

        //The goal is to find the first non-optional word, or the first optional word that is this rule
        this.lookAheadSet = new Set();
        let found = false;
        for (const word of this.words) {
            const checked = word.checkWordForLeftRecursion(parser, this, this.lookAheadSet);
            if (checked) {
                found = true;
                break;
            }
        }

        if (lookAheadSet !== null) {
            for (const wordValue of this.lookAheadSet) {
                lookAheadSet.add(wordValue);
            }
        }

        return found;
    }

    _getResult = (originalResult) => {
        if (GrammarForge.makeFullAST) {
            return new GrammarForge.ExpNode(this, originalResult);
        }
        else {
            let result = originalResult;
            if (this.keptWordIndexes.length > 0) {
                if (this.keptWordIndexes.length === 1) {
                    result = originalResult[this.keptWordIndexes[0]];
                }
                else {
                    result = this.keptWordIndexes.map(i => originalResult[i]);
                }

                //console.log(`${originalResult} -> ${result}`);

                if (this.execFunc === null)
                    return result;
            }
            
            if (this.execFunc === null) {
                if (result.length === 1) {
                    //console.log(`${result} -> ${result[0]}`);
                    return result[0];
                }
                else {
                    return result;
                }
            }
            else {
                if (this.automaticallyGeneratedFunc) {
                    if (this.rule !== null && this.rule.tag !== null) {
                        switch (this.rule.tag) {
                            case 'sl':
                                //sl knows it is only supposed to have 1 word.
                                if (Array.isArray(result)) {
                                    if (result.length === 0) {
                                        return new GrammarForge.EmptyNode();//This is better for allowing it to fall through when parsing failed.
                                        //throw new Error("Expected at least 1 statement in statement list, but got an empty array.");
                                    }

                                    const firstWordResult = result[0];
                                    if (!(firstWordResult instanceof GrammarForge.ExpNode))
                                        throw new Error("Expected an ExpNode result for statement list expression with 1 statement, but got: " + firstWordResult);

                                    if (result.length < 2)
                                        throw new Error("Expected at least 2 statements in statement list for it to be a + or * expression, but got: " + keptWordWordResult);

                                    return new GrammarForge.ExpNode(this, result);
                                }
                                else {
                                    if (!(result instanceof GrammarForge.ExpNode))
                                        throw new Error("Expected an ExpNode result for statement list expression with 1 statement, but got: " + keptWordWordResult);

                                    return result;
                                }
                            case 'stmt':
                                //Do nothing for stmt.
                                break;
                            case 'block':
                                return new GrammarForge.ExpNode(this, result);
                            case 'exp':
                                //Do nothing for exp.
                                break;
                            case 'stmt_exp':
                                //Do nothing for stmt_exp.
                                break;
                            default:
                                throw new Error(`No automatically generated function for expression with rule tag: ${this.rule.tag}`);
                        }
                    }

                    if (result instanceof GrammarForge.AstNode)
                        return new GrammarForge.ExpNode(this, result);

                    switch (this.tag) {
                        case 'declare':
                        case 'get':
                        case 'assign':
                        case 'print':
                        case 'while':
                        case 'foreach':
                        case 'if':
                        case 'return':
                        case 'func_declare':
                        case 'func_call':
                        case 'stmt_exp':
                        case 'post_inc':
                        case 'post_dec':
                        case 'pre_inc':
                        case 'pre_dec':
                            return new GrammarForge.ExpNode(this, result);
                        case 'par':
                            return result;
                        case 'continue':
                        case 'break':
                            return new GrammarForge.ExpNode(this, undefined);
                        case 'ternary':
                        case null:
                            if (result.length === 1) {
                                if (this.execFunc !== null) {
                                    return new GrammarForge.ExpNode(this, result[0]);
                                }
                                else {
                                    //console.log(`${result} -> ${result[0]}`);
                                    return result[0];
                                }
                            }
                            else {
                                if (this.execFunc === null) {
                                    return result;
                                }
                                else {
                                    let existingTermCount = 0;
                                    let existingTermIndex = -1;
                                    for (let i = 0; i < result.length; i++) {
                                        const item = result[i];
                                        if (Array.isArray(item) ? item.length > 0: !item.empty) {
                                            existingTermCount++;
                                            if (existingTermCount > 1)
                                                break;

                                            existingTermIndex = i;
                                        }
                                    }
                                    
                                    if (existingTermCount > 1) {
                                        return new GrammarForge.ExpNode(this, result);
                                    }
                                    else {
                                        if (existingTermIndex === -1)
                                            throw new Error("Expected to find at least 1 term in the result for an expression with an automatically generated function, but found none.  Result: " + result);

                                        //console.log(`${result} -> ${result[existingTermIndex]}`);
                                        return result[existingTermIndex];
                                    }
                                }
                            }
                        default:
                            throw new Error(`No automatically generated function for expression tag: ${this.tag}`);
                    }
                }
                else {
                    return new GrammarForge.ExpNode(this, result);
                }
            }
        }
    }

    getParseFunc = (parser) => {
        let funcIndex = parser.ruleSubFunctionLookup.get(this.subFuncString);
        if (funcIndex === undefined) {
            if (this.words.length === 0)
                throw new Error("Cannot create parse function for empty expression");

            const expressionString = this.expressionString;

            let func;
            const length = this.words.length;
            const wordFunctions = [];
            for (let i = 0; i < this.words.length; i++) {
                wordFunctions.push(this.words[i].getParseFunc(parser));
            }

            func = (tokenStream) => {
                const expStr = expressionString;
                
                const result = [];
                for (let i = 0; i < wordFunctions.length; i++) {
                    const wordResult = wordFunctions[i](tokenStream);
                    if (!wordResult)
                        throw new Error("Parse function for expression failed unexpectedly.");

                    result.push(wordResult);
                }

                const finalResult = this._getResult(result, this);
                
                //console.log(`finalResult: ${finalResult} of ${expStr}`);
                return finalResult;
            }

            funcIndex = parser.addSubFunction(this.subFuncString, func);
        }

        return parser.ruleSubFunctions[funcIndex];
    }

    getTryParseFunc = (parser) => {
        let funcIndex = parser.ruleTrySubFunctionLookup.get(this.subFuncString);
        if (funcIndex === undefined) {
            if (this.words.length === 0)
                throw new Error("Cannot create parse function for empty expression");

            const expressionString = this.expressionString;

            let tryFunc;
            const length = this.words.length;
            const wordTryFunctions = [];
            for (let i = 0; i < this.words.length; i++) {
                wordTryFunctions.push(this.words[i].getTryParseFunc(parser));
            }

            tryFunc = (tokenStream) => {
                const expStr = expressionString;

                const clonedStream = tokenStream.clone();
                const result = [];
                for (let i = 0; i < wordTryFunctions.length; i++) {
                    const wordResult = wordTryFunctions[i](clonedStream);
                    if (!wordResult)
                        return null;

                    result.push(wordResult);
                }

                tokenStream.index = clonedStream.index;
                
                const finalResult = this._getResult(result, this);
                //console.log(`finalResult: ${finalResult} of ${expStr}`);
                return finalResult;
            }

            funcIndex = parser.addTrySubFunction(this.subFuncString, tryFunc);
        }

        return parser.ruleTrySubFunctions[funcIndex];
    }

    setKeptWordIndexs(parser) {
        if (this.keptWordIndexes !== undefined) {
            if (this.gettingCheckedForKeptWordIndexes)
                return 1;//Indicates recursion.

            return this.keptWordIndexes.length;
        }
        
        this.gettingCheckedForKeptWordIndexes = true;

        this.keptWordIndexes = [];

        
        let count = 0;
        if (this.tag !== null && GrammarForge.Expression.operatorTagPrecedence.has(this.tag)) {
            for (let i = 0; i < this.words.length; i++) {
                const word = this.words[i];
                word.setKeptWordIndexs(parser);
                this.keptWordIndexes.push(i);
            }

            count = this.keptWordIndexes.length;
        }
        else {
            for (let i = 0; i < this.words.length; i++) {
                const word = this.words[i];
                let wordCount = word.setKeptWordIndexs(parser);
                if (wordCount > 0) {
                    count += wordCount;
                    this.keptWordIndexes.push(i);
                }
            }
        }

        delete this.gettingCheckedForKeptWordIndexes;

        return count;
    }

    getKeptWordsFromIndexs = (oTypes = null) => {
        const keptWords = [];
        for (let i = 0; i < this.keptWordIndexes.length; i++) {
            const word = this.words[this.keptWordIndexes[i]];
            keptWords.push(...word.getKeptWordsFromIndexs(oTypes));
        }

        return keptWords;
    }

    getChildren = (parser, childrenIndexSet) => {
        for (let j = 0; j < this.words.length; j++) {
            const word = this.words[j];
            word.getChildren(parser, childrenIndexSet);
        }
    }

    // walk = function*() {
    //     for (const word of this.words) {
    //         yield* word.walk();
    //     }
    // }

    toString() {
        return this.words.map(word => word.toString()).join(" ");
    }
}

GrammarForge.Expression.tags = new Set([
    'declare',//no_value - optional info after tag for not having to provide a value
    'assign',//no_declare - optional info after tag for not having to declare first
    'get',
    'while',
    'foreach',
    'for',
    'if',//Assumes the first stmt is the if body and the second is the else body (if present)
    'ternary',//Assumes the first exp is the condition, the second is the true case, and the third is the false case.
    'par',
    'break',
    'continue',
    'return',
    'func_declare',
    'func_call',
    'print',
    'post_inc',
    'post_dec',
    'pre_inc',
    'pre_dec',
    '+',
    '-',
    '*',
    '/',
    '%',
    '==',
    '!=',
    '<',
    '<=',
    '>',
    '>=',
    '&&',
    '||',
    '!',
    '^',
    '-#',
    '+#',
]);

GrammarForge.Expression.operatorTagPrecedence = new Map([
    ['||', 0],
    ['&&', 1],
    ['==', 2],
    ['!=', 2],
    ['<', 2],
    ['<=', 2],
    ['>', 2],
    ['>=', 2],
    ['+', 3],
    ['-', 3],
    ['*', 4],
    ['/', 4],
    ['%', 4],
    ['!', 5],
    ['-#', 5],
    ['+#', 5],
    ['^', 6],
]);

GrammarForge.Expression.operatorTagToOperator = new Map([
    ['+', '+'],
    ['-', '-'],
    ['*', '*'],
    ['/', '/'],
    ['%', '%'],
    ['==', '=='],
    ['!=', '!='],
    ['<', '<'],
    ['<=', '<='],
    ['>', '>'],
    ['>=', '>='],
    ['&&', '&&'],
    ['||', '||'],
    ['!', '!'],
    ['^', '^'],
    ['-#', '-'],
    ['+#', '+'],
])

GrammarForge.Expression.operatorTags = new Set([
    '+',
    '-',
    '*',
    '/',
    '%',
    '==',
    '!=',
    '<',
    '<=',
    '>',
    '>=',
    '&&',
    '||',
    '!',
    '^',
    '-#',
    '+#',
]);
