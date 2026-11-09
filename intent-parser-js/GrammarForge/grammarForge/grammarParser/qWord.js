"use strict";

GrammarForge.QWord = class QWord extends GrammarForge.Word {
    constructor(word, oType, delimiterWord = null) {
        if (!(word instanceof GrammarForge.Word))
            throw new Error(`QWord constructor: word must be an instance of GrammarForge.Word.`);

        if (!oType)
            throw new Error(`QWord constructor: oType is required and can't be null.`);

        if (delimiterWord !== null && !(delimiterWord instanceof GrammarForge.Word) || delimiterWord instanceof GrammarForge.QWord)
            throw new Error(`QWord constructor: delimiterWord must be an instance of GrammarForge.Word or null.`);

        if (delimiterWord !== null && oType !== 'ELLIPSIS')
            throw new Error(`QWord constructor: delimiterWord is only allowed with ELLIPSIS oType.`);

        super();
        this.word = word;
        this.oType = oType;
        this.delimiterWord = delimiterWord;
        this.qWordString = this.toString();
    }

    //Returns true if left recursion was checked and not found
    //Throws an error if left recursion is found
    //Returns false if this word was not a match, but is optional
    checkWordForLeftRecursion = (parser, expr, lookAheadSet) => {
        const checked = this.word.checkWordForLeftRecursion(parser, expr, lookAheadSet);
        if (checked && (this.oType === 'PLUS' || this.oType === 'ELLIPSIS'))
            return true;

        return false;
    }

    oTypeToString(oType) {
        switch (oType) {
            case "QUESTION":
                return "?";
            case "STAR":
                return "*";
            case "PLUS":
                return "+";
            case "ELLIPSIS":
                return `...${this.delimiterWord ? `<${this.delimiterWord.toString()}>` : ''}`;
            default:
                throw new Error(`QWord oTypeToString: Unknown oType ${oType}`);
        }
    }

    _getResultQuestion = (result) => {
        if (result === null)
            result = new GrammarForge.EmptyNode();

        if (GrammarForge.makeFullAST) {
            return [ 'QWORD', result, this.oType ];
        }
        else {
            return result;
        }
    }

    _getResult = (result, parser) => {
        if (GrammarForge.makeFullAST) {
            return [ 'QWORD', result, this.oType ];
        }
        else if (result.length === 1) {
            const stmt_rule = parser.exec.stmt_rule;
            if (stmt_rule !== null) {
                const expNode = result[0];
                if (expNode instanceof GrammarForge.ExpNode && expNode.expression.rule === stmt_rule)
                    return expNode;
            }
        }
        
        return result;
    }

    getParseFunc = (parser) => {
        let funcIndex = parser.ruleSubFunctionLookup.get(this.qWordString);
        if (funcIndex === undefined) {
            let func;
            switch (this.oType) {
                case "QUESTION": {
                        const wordTryParseFunc = this.word.getTryParseFunc(parser);
                        func = (tokenStream) => {
                            let result = null;
                            if (!tokenStream.end()) {
                                const clonedStream = tokenStream.clone();
                                const tryResult = wordTryParseFunc(clonedStream);
                                if (tryResult && clonedStream.index > tokenStream.index) {
                                    tokenStream.index = clonedStream.index;
                                    result = tryResult;
                                }
                            }

                            return this._getResultQuestion(result);
                        }
                    }
                    break;
                case "STAR": {
                        const wordTryParseFunc = this.word.getTryParseFunc(parser);
                        func = (tokenStream) => {
                            const result = [];
                            const clonedStream = tokenStream.clone();
                            for(;;) {
                                if (tokenStream.end())
                                    break;

                                const wordResult = wordTryParseFunc(clonedStream);
                                if (wordResult) {
                                    tokenStream.index = clonedStream.index;
                                    result.push(wordResult);
                                }
                                else {
                                    break;
                                }
                            }

                            return this._getResult(result, parser);
                        }
                    }
                    break;
                case "PLUS": {
                        const wordParseFunc = this.word.getParseFunc(parser);
                        const wordTryParseFunc = this.word.getTryParseFunc(parser);
                        func = (tokenStream) => {
                            const result = [];
                            const firstWordResult = wordParseFunc(tokenStream);
                            result.push(firstWordResult);
                            const clonedStream = tokenStream.clone();
                            for(;;) {
                                if (tokenStream.end())
                                    break;

                                const wordResult = wordTryParseFunc(clonedStream);
                                if (wordResult) {
                                    tokenStream.index = clonedStream.index;
                                    result.push(wordResult);
                                }
                                else {
                                    break;
                                }
                            }

                            return this._getResult(result, parser);
                        }
                    }
                    break;
                case "ELLIPSIS": {
                        const wordTryParseFunc = this.word.getTryParseFunc(parser);
                        const delimiterTryParseFunc = this.delimiterWord ? this.delimiterWord.getTryParseFunc(parser) : this.getCommaTryParseFunc(parser);
                        func = (tokenStream) => {
                            const result = [];
                            const clonedStream = tokenStream.clone();
                            const firstWordResult = wordTryParseFunc(clonedStream);
                            if (!firstWordResult)
                                return result;

                            result.push(firstWordResult);
                            tokenStream.index = clonedStream.index;
                            for(;;) {
                                if (tokenStream.end())
                                    break;

                                const delimiterResult = delimiterTryParseFunc(clonedStream);
                                if (!delimiterResult)
                                    break;

                                const wordResult = wordTryParseFunc(clonedStream);
                                if (!wordResult)
                                    break;

                                tokenStream.index = clonedStream.index;
                                result.push(wordResult);
                            }

                            return result;
                        }
                    }
                    break;
                default:
                    throw new Error(`Par type ${this.oType} not supported in getParseFunc`);
            }

            funcIndex = parser.addSubFunction(this.qWordString, func);
        }
        
        return parser.ruleSubFunctions[funcIndex];
    }

    getTryParseFunc = (parser) => {
        let funcIndex = parser.ruleTrySubFunctionLookup.get(this.qWordString);
        if (funcIndex === undefined) {
            let tryFunc;
            const wordTryParseFunc = this.word.getTryParseFunc(parser);
            switch (this.oType) {
                case "QUESTION":
                    tryFunc = (tokenStream) => {
                        let result = null;
                        if (!tokenStream.end()) {
                            const clonedStream = tokenStream.clone();
                            const tryResult = wordTryParseFunc(clonedStream);
                            if (tryResult && clonedStream.index > tokenStream.index) {
                                tokenStream.index = clonedStream.index;
                                result = tryResult;
                            }
                        }

                        return this._getResultQuestion(result);
                    }
                    break;
                case "STAR":
                    tryFunc = (tokenStream) => {
                        const result = [];
                        const clonedStream = tokenStream.clone();
                        for(;;) {
                            if (tokenStream.end())
                                break;

                            const wordResult = wordTryParseFunc(clonedStream);
                            if (wordResult) {
                                tokenStream.index = clonedStream.index;
                                result.push(wordResult);
                            }
                            else {
                                break;
                            }
                        }

                        return this._getResult(result, parser);
                    }
                    break;
                case "PLUS":
                    tryFunc = (tokenStream) => {
                        const clonedStream = tokenStream.clone();
                        const firstWordResult = wordTryParseFunc(clonedStream);
                        if (!firstWordResult)
                            return null;
                        
                        const result = [ firstWordResult ];
                        
                        tokenStream.index = clonedStream.index;
                        for(;;) {
                            if (tokenStream.end())
                                break;

                            const wordResult = wordTryParseFunc(clonedStream);
                            if (wordResult) {
                                tokenStream.index = clonedStream.index;
                                result.push(wordResult);
                            }
                            else {
                                break;
                            }
                        }

                        return this._getResult(result, parser);
                    }
                    break;
                case "ELLIPSIS": {
                        const delimiterTryParseFunc = this.delimiterWord ? this.delimiterWord.getTryParseFunc(parser) : this.getCommaTryParseFunc(parser);
                        tryFunc = (tokenStream) => {
                            const result = [];
                            const clonedStream = tokenStream.clone();
                            const firstWordResult = wordTryParseFunc(clonedStream);
                            if (!firstWordResult)
                                return result;

                            result.push(firstWordResult);
                            tokenStream.index = clonedStream.index;
                            for(;;) {
                                if (tokenStream.end())
                                    break;

                                const delimiterResult = delimiterTryParseFunc(clonedStream);
                                if (!delimiterResult)
                                    break;

                                const wordResult = wordTryParseFunc(clonedStream);
                                if (!wordResult)
                                    break;

                                tokenStream.index = clonedStream.index;
                                result.push(wordResult);
                            }

                            return result;
                        }
                    }
                    break;
                default:
                    throw new Error(`Par type ${this.oType} not supported in getParseFunc`);
            }

            funcIndex = parser.addTrySubFunction(this.qWordString, tryFunc);
        }

        return parser.ruleTrySubFunctions[funcIndex];
    }

    getCommaTryParseFunc = (parser) => {
        let funcIndex = parser.ruleTrySubFunctionLookup.get('COMMA');
        if (funcIndex === undefined) {
            const commaTerm = new GrammarForge.Term({ type: 'TOKEN', value: 'COMMA' });
            const tryFunc = commaTerm.getTryParseFunc(parser);
            return tryFunc;
        }

        return parser.ruleTrySubFunctions[funcIndex];
    }

    setKeptWordIndexs = (parser) => {
        const keptWordsCount = this.word.setKeptWordIndexs(parser);
        if (this.oType === 'ELLIPSIS') {
            if (this.delimiterWord)
                this.delimiterWord.setKeptWordIndexs(parser);

            return 1;
        }
        
        return keptWordsCount;
    }

    getKeptWordsFromIndexs = (oTypes = null) => {
        const keptWords = this.word.getKeptWordsFromIndexs(oTypes);
        if (this.oType === 'ELLIPSIS') {
            const delimiterKeptWords = this.delimiterWord ? this.delimiterWord.getKeptWordsFromIndexs(oTypes) : undefined;
            return [ [ this, keptWords, delimiterKeptWords ] ];
        }

        if (keptWords.length > 0 && oTypes?.has(this.oType))
            return [ [ this, keptWords ] ];

        return keptWords;
    }

    getChildren = (parser, childrenIndexSet) => {
        this.word.getChildren(parser, childrenIndexSet);
    }

    // walk = function*() {
    //     yield this;
    // }

    toString() {
        return `${this.word.toString()}${this.oTypeToString(this.oType)}`;
    }
}
