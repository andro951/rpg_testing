"use strict";

/*
grammar : stmt+
stmt    : rule | tknDef
rule    : IDENTIFIER (LBRACE IDENTIFIER RBRACE)? DEFINED_AS expList
expList : exp (ORBAR exp)*
exp     : wordBase+ (LBRACE IDENTIFIER (IDENTIFIER | INT | TOKEN)* RBRACE)?
wordBase: word
        | qWord
word    : term
        | par
qWord   : word oType
term    : IDENTIFIER 
        | TOKEN
        | SYMBOL
par     : LPAREN expList RPAREN
oType   : QUESTION
        | STAR
        | PLUS
tknDef  : TOKEN DEFINED_AS REGEX ((TOKEN | IDENTIFIER) | (LPAREN (TOKEN | IDENTIFIER) RPAREN))?
*/

{
    GrammarForge.GrammarParser = class GrammarParser {
        static tokens = [];
        static index = 0;
        static rules = [];
        static tokenDefinitions = [];
        static nextExpressionIndex = 0;
        static expressions = [];
        static expressionByRuleNameThenExpressionStringLookup = new Map();//Contains only expressions that are part of a rule.

        static parse(tokens) {
            GrammarParser.tokens = tokens;
            GrammarParser.index = 0;
            GrammarParser.rules = [];
            GrammarParser.tokenDefinitions = [];
            GrammarParser.nextExpressionIndex = 0;
            GrammarParser.expressions = [];
            GrammarParser.expressionByRuleNameThenExpressionStringLookup = new Map();
            return GrammarParser.grammar();
        }

        static match(type) {
            const token = GrammarParser.tokens[GrammarParser.index];
            if (token.type === type) {
                GrammarParser.index++;
            }
            else {
                throw new Error(`Expected token type ${type}, found ${token.type}`);
            }
        }

        static tryMatch(type) {
            const token = GrammarParser.tokens[GrammarParser.index];
            if (token.type === type) {
                GrammarParser.index++;
                return true;
            }
            else {
                return false;
            }
        }

        //grammar : stmt+
        static grammar() {
            if (GrammarParser.tokens.length === 0)
                throw new Error("No tokens to parse");

            while (GrammarParser.index < GrammarParser.tokens.length) {
                GrammarParser.stmt();
            }

            Object.freeze(GrammarParser.rules);
            //token definitions are frozen in the lexer constructor.
            Object.freeze(GrammarParser.expressions);
            Object.freeze(GrammarParser.expressionByRuleNameThenExpressionStringLookup);

            return { rules: GrammarParser.rules, tokenDefinitions: GrammarParser.tokenDefinitions, expressions: GrammarParser.expressions, expressionByRuleNameThenExpressionStringLookup: GrammarParser.expressionByRuleNameThenExpressionStringLookup };
        }
        
        static ruleSet = ["IDENTIFIER"];
        static tknDefSet = ["TOKEN"];
        static termSet = ["IDENTIFIER", "TOKEN", "SYMBOL"];
        static parSet = ["LPAREN"];
        static oTypeSet = ["QUESTION", "STAR", "PLUS", "ELLIPSIS"];
        static wordSet = GrammarParser.termSet.concat(GrammarParser.parSet);

        //stmt    : rule | tknDef
        static stmt() {
            const token = GrammarParser.tokens[GrammarParser.index];
            if (GrammarParser.ruleSet.includes(token.type)) {
                GrammarParser.rule();
            }
            else if (GrammarParser.tknDefSet.includes(token.type)) {
                GrammarParser.tknDef();
            }
            else {
                throw new Error(`Unexpected token type in stmt: ${token.type}`);
            }
        }

        //rule    : IDENTIFIER (LBRACE IDENTIFIER RBRACE)? DEFINED_AS expList
        static rule() {
            const token = GrammarParser.tokens[GrammarParser.index];
            const tokenName = token.value;
            GrammarParser.match("IDENTIFIER");
            let tag = null;
            if (GrammarParser.tryMatch("LBRACE")) {
                const metaToken = GrammarParser.tokens[GrammarParser.index];
                tag = metaToken.value;
                GrammarParser.match("IDENTIFIER");
                GrammarParser.match("RBRACE");
            }

            GrammarParser.match("DEFINED_AS");

            const expList = GrammarParser.expList(true, true);

            const rule = new GrammarForge.Rule(tokenName, expList, GrammarParser.rules.length, tag);
            const ruleMap = new Map();
            for (const exp of expList.expressions) {
                exp.rule = rule;
                ruleMap.set(exp.expressionString, exp);
            }

            GrammarParser.expressionByRuleNameThenExpressionStringLookup.set(tokenName, ruleMap);
            GrammarParser.rules.push(rule);
        }

        //expList : exp (ORBAR exp)*
        static expList(metaDataAllowed, calledFromRule) {
            if (metaDataAllowed === undefined)
                throw new Error(`expList: metaDataAllowed parameter is required.`);

            if (calledFromRule === undefined)
                throw new Error(`expList: calledFromRule parameter is required.`);

            let expressions = [];
            let index = 0;
            const exp = GrammarParser.exp(index++, metaDataAllowed, calledFromRule);
            expressions.push(exp);
            while (GrammarParser.index < GrammarParser.tokens.length && GrammarParser.tokens[GrammarParser.index].type === "ORBAR") {
                GrammarParser.match("ORBAR");
                const exp2 = GrammarParser.exp(index++, metaDataAllowed, calledFromRule);
                expressions.push(exp2);
            }
            
            return new GrammarForge.ExpList(expressions);
        }

        //exp     : wordBase+ (LBRACE IDENTIFIER (IDENTIFIER | INT | TOKEN)* RBRACE)?
        static exp(index, metaDataAllowed, calledFromRule) {
            if (metaDataAllowed === undefined)
                throw new Error(`exp: metaDataAllowed parameter is required.`);

            const words = [];
            while (GrammarParser.index < GrammarParser.tokens.length) {
                const token = GrammarParser.tokens[GrammarParser.index];
                if (GrammarParser.wordSet.includes(token.type)) {
                    const word = GrammarParser.wordBase();
                    if (word === undefined)
                        break;//word returns undefined if it sees a rule definition next.

                    words.push(word);
                } else {
                    break;
                }
            }

            if (words.length === 0) {
                throw new Error(`Expected at least one word in expression at index ${GrammarParser.index}`);
            }

            let metadata = [];
            if (GrammarParser.index < GrammarParser.tokens.length) {
                if (GrammarParser.tryMatch("LBRACE")) {
                    if (!metaDataAllowed)
                        throw new Error(`Metadata not allowed in this expression at index ${GrammarParser.index}`);

                    const token = GrammarParser.tokens[GrammarParser.index];
                    if (token.type !== "IDENTIFIER" && token.type !== 'MATH_SYMBOL' && token.type !== "TAG_OPEN" && token.type !== "TAG_CLOSE" && token.type !== "PLUS" && token.type !== "STAR")
                        throw new Error(`Unexpected token type in expression metadata: ${token.type}`);

                    GrammarParser.match(token.type);
                    metadata.push(token.value);
                    while (!GrammarParser.tryMatch("RBRACE")) {
                        const token = GrammarParser.tokens[GrammarParser.index];
                        if (token.type !== 'IDENTIFIER' && token.type !== 'INT' && token.type !== "TOKEN")
                            throw new Error(`Unexpected token type in expression metadata: ${token.type}`);

                        GrammarParser.match(token.type);
                        metadata.push(token.value);
                    }
                }
            }

            const expression = new GrammarForge.Expression(words, index, GrammarParser.nextExpressionIndex++, metadata);
            GrammarParser.expressions.push(expression);
            return expression;
        }

        static qWordCheck(wordResult) {
            if (GrammarParser.index < GrammarParser.tokens.length) {
                const token = GrammarParser.tokens[GrammarParser.index];
                if (GrammarParser.oTypeSet.includes(token.type)) {
                    GrammarParser.match(token.type);
                    if (GrammarParser.index < GrammarParser.tokens.length) {
                        const nextToken = GrammarParser.tokens[GrammarParser.index];
                        if (nextToken.type === "TAG_OPEN") {
                            if (token.type !== "ELLIPSIS")
                                throw new Error(`<TAG> is only allowed after an ELLIPSIS (...).  Not allowed after a ${token.type} (${token.value}).  Found at index ${GrammarParser.index}`);

                            GrammarParser.match("TAG_OPEN");
                            const tagWordResult = GrammarParser.word();
                            if (tagWordResult === undefined)
                                throw new Error(`Expected word for tag, found ${nextToken.type} (${nextToken.value}).  Found at index ${GrammarParser.index}`);

                            GrammarParser.match("TAG_CLOSE");

                            const qWord = new GrammarForge.QWord(wordResult, token.type, tagWordResult);

                            return this.qWordCheck(qWord);
                        }
                    }

                    const qWord = new GrammarForge.QWord(wordResult, token.type);

                    return this.qWordCheck(qWord);
                }
            }

            return wordResult;
        }

        // wordBase: word
        // | qWord
        // qWord   : word oType
        static wordBase() {
            const wordResult = GrammarParser.word();
            if (wordResult === undefined)
                return undefined;

            return GrammarParser.qWordCheck(wordResult);
        }

        // word    : term
        // | par
        static word() {
            const token = GrammarParser.tokens[GrammarParser.index];
            if (GrammarParser.termSet.includes(token.type)) {
                if (token.type === "IDENTIFIER" || token.type === "TOKEN") {
                    if (GrammarParser.index + 1 < GrammarParser.tokens.length) {
                        const nextToken = GrammarParser.tokens[GrammarParser.index + 1];
                        if (nextToken.type === "DEFINED_AS") {
                            return undefined; //signal that a new rule or token definition is starting
                        }
                        else if (nextToken.type === "LBRACE") {
                            if (GrammarParser.index + 4 < GrammarParser.tokens.length) {
                                const tokenAfterBraces = GrammarParser.tokens[GrammarParser.index + 4];
                                if (tokenAfterBraces.type === "DEFINED_AS") {
                                    return undefined; //signal that a new rule or token definition is starting
                                }
                            }
                        }
                    }
                }

                return GrammarParser.term();
            }
            else if (GrammarParser.parSet.includes(token.type)) {
                return GrammarParser.par();
            }
            else {
                throw new Error(`Unexpected token type in word: ${token.type}`);
            }
        }

        //term    : IDENTIFIER 
        //        | TOKEN
        //        | SYMBOL
        static term() {
            const token = GrammarParser.tokens[GrammarParser.index];
            if (this.termSet.includes(token.type)) {
                GrammarParser.match(token.type);
                return new GrammarForge.Term(token);
            }
            else {
                throw new Error(`Unexpected token type in term: ${token.type}`);
            }
        }

        //par     : LPAREN expList RPAREN
        static par() {
            GrammarParser.match("LPAREN");
            const expList = GrammarParser.expList(false, false);
            GrammarParser.match("RPAREN");
            
            return new GrammarForge.Par(expList);
        }

        //tknDef  : TOKEN DEFINED_AS REGEX ((TOKEN | IDENTIFIER) | (LPAREN (TOKEN | IDENTIFIER) RPAREN))?
        static tknDef() {
            const token1 = GrammarParser.tokens[GrammarParser.index];
            const tokenName = token1.value;
            GrammarParser.match("TOKEN");
            GrammarParser.match("DEFINED_AS");
            const token2 = GrammarParser.tokens[GrammarParser.index];
            if (token2.type !== "REGEX")
                throw new Error(`Unexpected token type in tknDef: ${token2.type}`);

            GrammarParser.match("REGEX");
            let tag = null;
            if (GrammarParser.index + 1 < GrammarParser.tokens.length) {
                const token3 = GrammarParser.tokens[GrammarParser.index];
                if (token3.type === "LPAREN") {
                    GrammarParser.match("LPAREN");
                    const token4 = GrammarParser.tokens[GrammarParser.index];
                    if (token4.type === "TOKEN" || token4.type === "IDENTIFIER") {
                        tag = token4.value;
                        GrammarParser.match(token4.type);
                        GrammarParser.match("RPAREN");
                    }
                }
                else {
                    if (token3.type === "TOKEN" || token3.type === "IDENTIFIER") {
                        let hasTag = false;
                        if (GrammarParser.index + 1 >= GrammarParser.tokens.length) {
                            hasTag = true;
                        }
                        else {
                            const token4 = GrammarParser.tokens[GrammarParser.index + 1];
                            if (token4.type === "TOKEN" || token4.type === "IDENTIFIER")
                                hasTag = true;
                        }

                        if (hasTag) {
                            tag = token3.value;
                            GrammarParser.match(token3.type);
                        }
                    }
                }
            }

            const regex = GrammarForge.stringToRegex(token2.value);
            const tokenDef = new GrammarForge.TokenDefinition(tokenName, regex, tag);
            GrammarParser.tokenDefinitions.push(tokenDef);
        }

        static rulesToString() {
            return GrammarParser.rules.map(rule => rule.toString()).join("\n");
        }

        static tokenDefinitionsToString() {
            return GrammarParser.tokenDefinitions.map(tknDef => tknDef.toString()).join("\n");
        }
    }
}
