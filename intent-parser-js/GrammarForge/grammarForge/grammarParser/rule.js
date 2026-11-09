"use strict";

GrammarForge.Rule = class Rule {
    constructor(name, expList, index, tag = null) {
        if (!name)
            throw new Error("name is required");

        if (!(expList instanceof GrammarForge.ExpList))
            throw new Error("expList must be a GrammarForge.ExpList");

        if (index === undefined || index === null || typeof index !== 'number' || index < 0)
            throw new Error("index must be a non-negative number");

        if (tag !== null && typeof tag !== 'string')
            throw new Error("tag must be a string or null");

        this.name = name;
        this.expList = expList;
        this.index = index;
        this.tag = tag;
        this.checkTagAndExpressionsMetadata();
    }

    checkTagAndExpressionsMetadata = () => {
        this.checkTag();
        const tag = this.tag;
        for (const expr of this.expList.expressions) {
            expr.checkMetadata(this);
        }

        if (tag !== this.tag) {
            this.checkTag();
        }
    }
    
    checkLeftRecursion = (parser, lookAheadSet = null) => {
        if (this.checkingLeftRecursion)
            throw new Error(`Left recursion detected in rule: ${this.name}.  This means that the rule can call itself without consuming any tokens.  The parser is a LL1 recursive descent parser with backtracking. Left recursion is not supported.  Left recursion means the first non-optional word in an expression is the same as the rule name.`);

        this.checkingLeftRecursion = true;

        let foundAll = true;
        for (const expr of this.expList.expressions) {
            const checked = expr.checkWordsForLeftRecursion(parser, lookAheadSet);
            if (!checked) {
                foundAll = false;
            }
        }

        delete this.checkingLeftRecursion;

        return foundAll;
    }

    checkTag = () => {
        if (this.tag === null)
            return;

        if (GrammarForge.Rule.tags.has(this.tag))
            return;

        if (!GrammarForge.Expression.tags.has(this.tag)) {
            if (GrammarForge.Expression.operatorTags.has(this.tag)) {
                if (this.expList.expressions.length === 1) {
                    const expression = this.expList.expressions[0];
                    if (expression.words.length === 1) {
                        if (expression.metadata.length === 0) {
                            expression.metadata.push(this.tag);
                            expression.tag = this.tag;
                            this.tag = null;
                            expression.checkMetadata(this);
                            return;
                        }
                    }
                }

                throw new Error(`Operator tag ${this.tag} can only be used on rules with a single expression containing a single operator token.  Rule: ${this.name}`);
            }
            else {
                throw new Error(`Invalid rule tag: ${this.tag}`);
            }
        }

        const tag = this.tag;
        this.tag = null;
        for (const expr of this.expList.expressions) {
            if (expr.metadata.length !== 0)
                throw new Error(`${tag} was placed on rule: ${this.name}, but it is an expression tag.  Expression: ${expr.expressionString} already has a tag, ${expr.metadata[0]}.  An expression cannot have multiple tags.`);
            
            expr.metadata.push(tag);
            expr.tag = tag;
            expr.checkMetadata(this);
        }
    }

    _getResult = (result) => {
        if (GrammarForge.makeFullAST) {
            return [ 'RULE', result, this.name ];
        }
        else {
            return result;
        }
    }

    createParseFunctions = (parser) => {
        if (parser.ruleFunctions[this.index] !== null)
            throw new Error(`Parse function already exists for rule index ${this.index}`);

        const expListParseFunc = this.expList.getParseFunc(parser);
        const func = (tokenStream) => {
            const result = expListParseFunc(tokenStream);

            return this._getResult(result);
        }

        const expListTryParseFunc = this.expList.getTryParseFunc(parser);
        const tryFunc = (tokenStream) => {
            const tryResult = expListTryParseFunc(tokenStream);
            if (!tryResult)
                return null;

            return this._getResult(tryResult);
        }

        parser.ruleFunctions[this.index] = func.bind(parser);
        parser.ruleTryFunctions[this.index] = tryFunc.bind(parser);
    }

    checkMakeDefaultExecFunctions = (exec) => {
        if (this.tryMakeDefaultExecFunctionFromRuleTag(exec) === true)
            return;

        for (let i = 0; i < this.expList.expressions.length; i++) {
            this.tryMakeDefaultExecFunctionFromTag(exec, i);
        }

        for (let i = 0; i < this.expList.expressions.length; i++) {
            this.tryMakeDefaultExpExecFunc(exec, i);
        }
    }

    tryMakeDefaultExecFunctionFromRuleTag = (exec) => {
        const tag = this.tag;
        if (tag === null)
            return false;

        if (tag !== 'block' && tag !== 'sl')
            return false;

        for (let i = 0; i < this.expList.expressions.length; i++) {
            const expression = this.expList.expressions[i];
            let func = null;
            switch (tag) {
                case 'block': {
                        const [ stmtListIndex ] = this.getTaggedWordIndices(exec, expression, ['sl'], tag);
                        if (stmtListIndex !== 0)
                            throw new Error(`For the block tag, the stmt list must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                        const defaultFunc = exec.defaultExecFunctions.get("block");
                        func = (stmts) => defaultFunc(stmts);
                    }

                    break;
                case 'sl': {
                        const [ stmtIndex ] = this.getTaggedWordIndices(exec, expression, ['stmt'], tag);
                        if (stmtIndex !== 0)
                            throw new Error(`For the sl tag, the stmt must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);
                        
                        const defaultFunc = exec.defaultExecFunctions.get("sl");
                        func = (stmts) => defaultFunc(stmts);
                    }

                    break;
            }

            if (func === null)
                throw new Error(`Fell through the switch trying to make default exec function for rule tag: ${tag}, rule: ${this.name}, expression index: ${i}, expression: ${expression.expressionString}`);
            
            expression.execFunc = func;
        }

        return true;
    }

    tryMakeDefaultExecFunctionFromTag = (exec, expressionIndex) => {
        const expression = this.expList.expressions[expressionIndex];
        const tag = expression.tag;
        if (tag === null)
            return;

        if (expression.execFunc !== null) {
            console.warn(`A rule was tagged as ${tag}:\n${this.toString()}\nbut the expression that looks like a ${tag} expression already has a user-defined exec function.  Skipping default ${tag} function generation for this expression:\n${expression.expressionString}`);
            return;
        }

        let func = null;
        switch (tag) {
            case 'while': {
                    const [ expIndex, stmtIndex ] = this.getTaggedWordIndices(exec, expression, ['exp', 'stmt'], tag);
                    
                    const defaultFunc = exec.defaultExecFunctions.get("while");
                    func = (arr) => defaultFunc(arr[expIndex], arr[stmtIndex]);
                }
                break;
            case 'foreach' : {
                    const [ varIndex, expIndex, stmtIndex ] = this.getTaggedWordIndices(exec, expression, ['var', 'exp', 'stmt'], tag);
                    
                    const defaultFunc = exec.defaultExecFunctions.get("foreach");
                    func = (arr) => defaultFunc(arr[varIndex], arr[expIndex], arr[stmtIndex]);
                }
                break;
            case 'assign': {
                    const [ varIndex, expIndex ] = this.getTaggedWordIndices(exec, expression, ['var', 'exp'], tag);

                    let defaultFunc;
                    const metadata = expression.metadata;
                    if (metadata.length > 1) {
                        const tagInfo = metadata[1];
                        if (tagInfo !== 'no_declare')
                            throw new Error(`Expression has a tag with unrecognized info: ${tagInfo}.  The only supported info for assign is 'no_declare'.  expression: ${expression.expressionString} in rule: ${this.name}, tag: ${metadata.join(" ")}`);
                    
                        defaultFunc = exec.defaultExecFunctions.get("assign no_declare");
                    }
                    else {
                        defaultFunc = exec.defaultExecFunctions.get("assign");
                    }

                    func = (arr) => defaultFunc(arr[varIndex], arr[expIndex]);
                }

                break;
            case 'print': {
                    const [ expIndex ] = this.getTaggedWordIndices(exec, expression, ['exp'], tag);
                    if (expIndex !== 0)
                        throw new Error(`For the print tag, the expression must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                    const defaultFunc = exec.defaultExecFunctions.get("print");
                    func = (exp) => defaultFunc(exp);
                }

                break;
            case 'declare': {
                    const metadata = expression.metadata;
                    if (metadata.length > 1) {
                        const tagInfo = metadata[1];
                        if (tagInfo !== 'no_value')
                            throw new Error(`Expression has a tag with unrecognized info: ${tagInfo}.  The only supported info for declare is 'no_value'.  expression: ${expression.expressionString} in rule: ${this.name}, tag: ${metadata.join(" ")}`);

                        const defaultFunc = exec.defaultExecFunctions.get("declare no_value");
                        const [ varIndex ] = this.getTaggedWordIndices(exec, expression, ['var'], tag);
                        if (varIndex !== 0)
                            throw new Error(`For the declare tag with no_value, the variable must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                        func = (varName) => defaultFunc(varName);
                    }
                    else {
                        const [ varIndex, expIndex ] = this.getTaggedWordIndices(exec, expression, ['var', 'exp'], tag);
                        const defaultFunc = exec.defaultExecFunctions.get("declare");
                        func = (arr) => defaultFunc(arr[varIndex], arr[expIndex]);
                    }
                }

                break;
            case 'get': {
                    const defaultFunc = exec.defaultExecFunctions.get("get");
                    const [ varIndex ] = this.getTaggedWordIndices(exec, expression, ['var'], tag);
                    if (varIndex !== 0)
                        throw new Error(`For the get tag, the variable must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                    func = (varName) => defaultFunc(varName);
                }

                break;
            case 'par': {
                    const [ expIndex ] = this.getTaggedWordIndices(exec, expression, ['exp'], tag);
                    if (expIndex !== 0)
                        throw new Error(`For the par tag, the expression must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                    const defaultFunc = exec.defaultExecFunctions.get("par");
                    func = (exp) => defaultFunc(exp);
                }

                break;
            case 'break': {
                    const empty = this.getTaggedWordIndices(exec, expression, [], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("break");
                    func = () => defaultFunc();
                }

                break;
            case 'continue': {
                    const empty = this.getTaggedWordIndices(exec, expression, [], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("continue");
                    func = () => defaultFunc();
                }

                break;
            case 'return': {
                    try {
                        const [ optionalIndex ] = this.getTaggedWordIndices(exec, expression, ['QUESTION'], tag);
                        if (optionalIndex !== 0)
                            throw new Error(`For the return tag with an optional expression, the optional must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                        const defaultFunc = exec.defaultExecFunctions.get("return optional");
                        func = (optionalExp) => defaultFunc(optionalExp);
                    }
                    catch (e) {
                        if (e.message.startsWith("No optional non-terminal found")) {
                            const [ expIndex ] = this.getTaggedWordIndices(exec, expression, ['exp'], tag);
                            if (expIndex !== 0)
                                throw new Error(`For the return tag, the expression must be the first non-terminal in the expression.  expression: ${expression.expressionString} in rule: ${this.name}`);

                            const defaultFunc = exec.defaultExecFunctions.get("return");
                            func = (exp) => defaultFunc(exp);
                        }
                        else {
                            throw e;
                        }
                    }
                }

                break;
            case 'func_declare': {
                    const [ varIndex, optionalIndex, blockIndex ] = this.getTaggedWordIndices(exec, expression, ['var', 'QUESTION', 'block'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("func_declare");
                    func = (arr) => defaultFunc(arr[varIndex], arr[optionalIndex], arr[blockIndex]);
                }

                break;
            case 'func_call': {
                    const [ varIndex, optionalIndex ] = this.getTaggedWordIndices(exec, expression, ['var', 'QUESTION'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("func_call");
                    func = (arr) => defaultFunc(arr[varIndex], arr[optionalIndex]);
                }

                break;
            case 'post_inc': {
                    const [ varIndex ] = this.getTaggedWordIndices(exec, expression, ['var'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("post_inc");
                    func = (varName) => defaultFunc(varName);
                }

                break;
            case 'post_dec': {
                    const [ varIndex ] = this.getTaggedWordIndices(exec, expression, ['var'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("post_dec");
                    func = (varName) => defaultFunc(varName);
                }

                break;
            case 'pre_inc': {
                    const [ varIndex ] = this.getTaggedWordIndices(exec, expression, ['var'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("pre_inc");
                    func = (varName) => defaultFunc(varName);
                }

                break;
            case 'pre_dec': {
                    const [ varIndex ] = this.getTaggedWordIndices(exec, expression, ['var'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("pre_dec");
                    func = (varName) => defaultFunc(varName);
                }

                break;
            case 'if' : {
                    const [ expIndex, stmtIndex, elseStmtIndex ] = this.getTaggedWordIndices(exec, expression, ['exp', 'stmt', 'stmt'], tag);

                    const defaultFunc = exec.defaultExecFunctions.get("if");
                    func = (arr) => defaultFunc(arr[expIndex], arr[stmtIndex], arr[elseStmtIndex]);
                }

                break;
            case 'ternary' : {
                    const [ firstIndex, exp1Index, exp2Index ] = this.getTaggedWordIndices(exec, expression, ['FIRST', 'exp', 'exp'], tag);
                    if (firstIndex !== 0 || exp1Index !== 1 || exp2Index !== 2)
                        throw new Error(`For the ternary tag, the indices are incorrect.  expression: ${expression.expressionString} in rule: ${this.name}`);

                    const defaultFunc = exec.defaultExecFunctions.get("ternary");
                    func = (arr) => defaultFunc(...arr);
                }

                break;
            default:
                return;
        }

        if (func === null)
            throw new Error(`Fell through the switch trying to make default exec function for rule: ${this.name}, expression index: ${expressionIndex}, tag: ${tag}`);

        //console.log(`Auto-generated default ${tag} exec function for rule: ${this.name}, expression index: ${expressionIndex}, expression: ${expression.expressionString}`);
        expression.execFunc = func;
    }

    getRulesFromTags(exec, rulesTags, tag, expression) {
        return rulesTags.map(rt => {
            const rule = exec.ruleTagLookup.get(rt);
            if (!rule) {
                if (rt === 'FIRST' || rt === 'QUESTION' || rt === 'PLUS' || rt === 'STAR')
                    return { name: rt };//Dummy rule for qWord

                if (rt === 'ELLIPSIS') {
                    throw new Error(`ELLIPSIS is always returned instead of its children.  It should not be used in the rulesTags for a tag.  expression: ${expression.expressionString}`);
                }

                throw new Error(`Found a ${tag} tag on expression: ${expression.expressionString}, but no rule tagged as ${rt} found.`);
            }

            return rule;
        });
    }

    validateKeptWordsCount(keptWords, rules, tag, expression) {
        if (keptWords.length !== rules.length)
            throw new Error(`Found a ${tag} tag on expression: ${expression.expressionString}, but ${tag} requires exactly ${rules.length} non-terminals. Found ${keptWords.length}`);
    }

    assignIndices(keptWords, rules, tag, expression) {
        const indices = Array(rules.length).fill(-1);
        const keptWordUsed = Array(keptWords.length).fill(false);

        let firstIndex = -1;
        for (let j = 0; j < rules.length; j++) {
            const rule = rules[j];
            if (rule.name === 'FIRST') {
                firstIndex = j;
                break;
            }
        }

        if (firstIndex !== -1) {
            indices[firstIndex] = 0;
            keptWordUsed[0] = true;
        }

        for (let i = 0; i < rules.length; i++) {
            if (firstIndex === i)
                continue;

            const rule = rules[i];
            for (let j = 0; j < keptWords.length; j++) {
                if (keptWordUsed[j])
                    continue;

                if (Array.isArray(keptWords[j])) {
                    const [ qWord, words ] = keptWords[j];
                    if (!(qWord instanceof GrammarForge.QWord))
                        throw new Error(`Found a ${tag} tag with an optional non-terminal, but the non-terminal is not a QWord: ${expression.expressionString}`);

                    indices[i] = j;
                    keptWordUsed[j] = true;
                    break;
                }
                else {
                    const word = keptWords[j];
                    if (!(word instanceof GrammarForge.Term))
                        continue;

                    if (word.type !== "IDENTIFIER")
                        throw new Error(`Found a ${tag} tag, expected IDENTIFIER: ${word.string}`);

                    if (rule.name === word.value) {
                        indices[i] = j;
                        keptWordUsed[j] = true;
                        break;
                    }
                }
            }
        }

        for (let i = 0; i < indices.length; i++) {
            if (indices[i] === -1)
                throw new Error(`No ${rules[i].name} non-terminal found: ${expression.expressionString}`);

            if (!keptWordUsed[i])
                throw new Error(`Non-terminal for rule ${rules[i].name} was not used: ${expression.expressionString}`);
        }

        return indices;
    }

    getTaggedWordIndices(exec, expression, rulesTags, tag) {
        const rules = this.getRulesFromTags(exec, rulesTags, tag, expression);
        let oTypes = new Set();
        for (const rule of rules) {
            if (rule.name === 'QUESTION' || rule.name === 'PLUS' || rule.name === 'STAR') {
                oTypes.add(rule.name);
                break;
            }
        }

        const keptWords = expression.getKeptWordsFromIndexs(oTypes);
        this.validateKeptWordsCount(keptWords, rules, tag, expression);
        return this.assignIndices(keptWords, rules, tag, expression);
    }

    tryMakeDefaultExpExecFunc = (exec, expressionIndex) => {
        if (this.isExpRule !== true)
            return;

        const expression = this.expList.expressions[expressionIndex];
        if (expression.tag !== null)
            return;

        const hasExecFunc = expression.execFunc !== null;// || expression.requiredArgIndexes !== undefined;
        if (expression.words.length === 0) {
            throw new Error(`Found an exp rule with an empty expression in rule: ${this.name}, expression: ${expression.expressionString}.  exp rules must have at least one word.`);
        }
        else if (expression.words.length === 1) {
            //exp_n : exp_{n+1}
            const firstWord = expression.words[0];
            if (this.isBaseExpRule(exec, firstWord)) {
                if (this.name === firstWord.value) {
                    if (!hasExecFunc)
                        throw new Error(`Found an exp rule recursion in rule: ${this.name}, expression: ${expression.expressionString}.  The parser is a LL1 recursive desent parser with backtracking. Left recursion is not supported.`);
                }
            }

            return;
        }
        else if (expression.words.length > 3) {
            if (!hasExecFunc)
                console.warn(`Found an rule that is a child of your 'exp' rule, but it has more than 3 words (words: ${expression.words.length}).  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

            return;
        }

        let func = null;
        // exp_n : exp_{n+1} (op_n exp_{n+1})*              //left associative ((a op b) op c) op d
        // exp_n : exp_{n+1} (op_n exp_{n+1})+ | exp_{n+1}  //left associative ((a op b) op c) op d
        // exp_n : exp_{n+1} (op_n exp_n)?                  //right associative a op (b op (c op d))
        // exp_n : exp_{n+1} op_n exp_n | exp_{n+1}         //right associative a op (b op (c op d))
        // exp_n : op_n exp_n | exp_{n+1}
        if (expression.words.length === 2) {
            const firstWord = expression.words[0];
            const secondWord = expression.words[1];
            if (this.isBaseExpRule(exec, firstWord)) {
                if (firstWord.value === this.name)
                    throw new Error(`Found an exp rule recursion in rule: ${this.name}, expression: ${expression.expressionString}.  The parser is a LL1 recursive desent parser with backtracking. Left recursion is not supported.`);

                // exp_n : exp_{n+1} (op_n exp_{n+1})*
                // exp_n : exp_{n+1} (op_n exp_{n+1})+ | exp_{n+1}
                // exp_n : exp_{n+1} (op_n exp_n)?
                if (!(secondWord instanceof GrammarForge.QWord)) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its second word is not a QWord.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);
                }

                if (!(secondWord.word instanceof GrammarForge.Par)) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its second word is not a Par.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                    return;
                }
                
                const parExpression = secondWord.word.expList.expressions[0];
                if (parExpression.words.length !== 2) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its second word Par does not have exactly 2 words.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                    return;
                }

                const parFirstWord = parExpression.words[0];
                const parSecondWord = parExpression.words[1];
                if (!this.isOpRule(exec, parFirstWord)) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its second word Par's first word is not an op rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                    return;
                }

                if (!this.isBaseExpRule(exec, parSecondWord)) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its second word Par's second word is not a base exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                    return;
                }

                const questionPar = secondWord.oType === 'QUESTION';
                if (questionPar) {
                    // exp_n : exp_{n+1} (op_n exp_n)?
                    if (parSecondWord.value !== this.name) {
                        if (!hasExecFunc)
                            console.warn(`Found an rule that is a child of your 'exp' rule, but its second word Par's second word is not the same as the exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                        return;
                    }
                }
                else {
                    // exp_n : exp_{n+1} (op_n exp_{n+1})*
                    // exp_n : exp_{n+1} (op_n exp_{n+1})+ | exp_{n+1}
                    if (parSecondWord.value === this.name) {
                        if (!hasExecFunc)
                            console.warn(`Found an rule that is a child of your 'exp' rule, but its second word Par's second word is the same as the exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                        return;
                    }
                }

                if (hasExecFunc) {
                    console.warn(`Found an rule that is a child of your 'exp' rule, but it already has a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);
                    return;
                }

                //Need to get the precedence level by checking which ops this op_n has in it.
                const ops = [];
                this.getOps(exec, parFirstWord, ops);
                if (ops.length === 0)
                    throw new Error(`No operators found for op rule: ${parFirstWord.string} in expression: ${expression.expressionString} in rule: ${this.name}`);

                const firstOp = ops[0];
                let precedenceLevel = GrammarForge.Expression.operatorTagPrecedence.get(firstOp);
                if (precedenceLevel === undefined)
                    throw new Error(`No precedence level found for operator: ${firstOp} in expression: ${expression.expressionString} in rule: ${this.name}`);

                for (let i = 1; i < ops.length; i++) {
                    const op = ops[i];
                    const opPrecedenceLevel = GrammarForge.Expression.operatorTagPrecedence.get(op);
                    if (opPrecedenceLevel === undefined)
                        throw new Error(`No precedence level found for operator: ${op} in expression: ${expression.expressionString} in rule: ${this.name}`);

                    if (opPrecedenceLevel !== precedenceLevel)
                        throw new Error(`Mismatched precedence levels found for operators in op rule: ${parFirstWord.string} in expression: ${expression.expressionString} in rule: ${this.name}.  All operators in an op rule must have the same precedence level.  Found operators: ${ops.join(", ")}`);
                }

                const funcMap = exec.opFunctions[precedenceLevel];
                if (!funcMap)
                    throw new Error(`No default op functions found at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

                if (questionPar) {
                    func = (arr) => {
                        const [ exp_n_1, optionalArr ] = arr;
                        const left = exp_n_1.exec();
                        if (Array.isArray(optionalArr)) {
                            const [ op_n, exp_n ] = optionalArr;
                            const right = exp_n.exec();
                            const op = op_n.exec();
                            const baseFunc = funcMap.get(op);
                            if (!baseFunc)
                                throw new Error(`No default op function found for operator: ${op} at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

                            return baseFunc(left, right);
                        }
                        else {
                            if (!optionalArr.empty)
                                throw new Error(`Expected optional array for question par, but got non-array: ${optionalArr} in expression: ${expression.expressionString} in rule: ${this.name}`);

                            return left;
                        }
                    }
                }
                else {
                    func = (arr) => {
                        const [ exp_n_1, optionalArr ] = arr;
                        let result = exp_n_1.exec();
                        if (Array.isArray(optionalArr)) {
                            for (const [ op_n, exp_n ] of optionalArr) {
                                const right = exp_n.exec();
                                const op = op_n.exec();
                                const baseFunc = funcMap.get(op);
                                if (!baseFunc)
                                    throw new Error(`No default op function found for operator: ${op} at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

                                result = baseFunc(result, right);
                            }

                            return result;
                        }
                        else {
                            if (!optionalArr.empty)
                                throw new Error(`Expected optional array for star par, but got non-array: ${optionalArr} in expression: ${expression.expressionString} in rule: ${this.name}`);

                            return result;
                        }
                    }
                }
            }
            else if (this.isBaseExpRule(exec, secondWord)) {
                // exp_n : op_n exp_n | exp_{n+1}
                if (secondWord.value !== this.name) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its second word is not the same as the exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                    return;
                }

                if (!this.isOpRule(exec, firstWord)) {
                    if (!hasExecFunc)
                        console.warn(`Found an rule that is a child of your 'exp' rule, but its first word is not an op rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                    return;
                }

                if (hasExecFunc) {
                    console.warn(`Found an rule that is a child of your 'exp' rule, but it already has a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);
                    return;
                }

                //Need to get the precedence level by checking which ops this op_n has in it.
                const ops = [];
                this.getOps(exec, firstWord, ops);
                if (ops.length === 0)
                    throw new Error(`No operators found for op rule: ${firstWord.string} in expression: ${expression.expressionString} in rule: ${this.name}`);

                const firstOp = ops[0];
                let precedenceLevel = GrammarForge.Expression.operatorTagPrecedence.get(firstOp);
                if (precedenceLevel === undefined)
                    throw new Error(`No precedence level found for operator: ${firstOp} in expression: ${expression.expressionString} in rule: ${this.name}`);

                for (let i = 1; i < ops.length; i++) {
                    const op = ops[i];
                    const opPrecedenceLevel = GrammarForge.Expression.operatorTagPrecedence.get(op);
                    if (opPrecedenceLevel === undefined)
                        throw new Error(`No precedence level found for operator: ${op} in expression: ${expression.expressionString} in rule: ${this.name}`);

                    if (opPrecedenceLevel !== precedenceLevel)
                        throw new Error(`Mismatched precedence levels found for operators in op rule: ${firstWord.string} in expression: ${expression.expressionString} in rule: ${this.name}.  All operators in an op rule must have the same precedence level.  Found operators: ${ops.join(", ")}`);
                }

                const funcMap = exec.opFunctions[precedenceLevel];
                if (!funcMap)
                    throw new Error(`No default op functions found at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

                func = (arr) => {
                    const [ op_n, exp_n ] = arr;
                    const op = op_n.exec();
                    const value = exp_n.exec();
                    const baseFunc = funcMap.get(op);
                    if (!baseFunc)
                        throw new Error(`No default op function found for operator: ${op} at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

                    return baseFunc(value);
                }
            }
            else {
                if (!hasExecFunc)
                    console.warn(`Found a rule that is a child of your 'exp' rule, but neither its first nor second word is a base exp rule and it does not have a provided execution function.  expression: ${expression.expressionString} in rule: ${this.name}`);

                return;
            }
        }
        else {
            // exp_n : exp_{n+1} op_n exp_n | exp_{n+1}         //right associative a op (b op (c op d))
            const firstWord = expression.words[0];
            const secondWord = expression.words[1];
            const thirdWord = expression.words[2];

            if (!this.isBaseExpRule(exec, firstWord)) {
                if (!hasExecFunc)
                    console.warn(`Found an rule that is a child of your 'exp' rule, but its first word is not a base exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                return;
            }

            if (!this.isOpRule(exec, secondWord)) {
                if (!hasExecFunc)
                    console.warn(`Found an rule that is a child of your 'exp' rule, but its second word is not an op rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                return;
            }

            if (!this.isBaseExpRule(exec, thirdWord)) {
                if (!hasExecFunc)
                    console.warn(`Found an rule that is a child of your 'exp' rule, but its third word is not a base exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                return;
            }

            if (firstWord.value === this.name)
                throw new Error(`Found an exp rule recursion in rule: ${this.name}, expression: ${expression.expressionString}.  The parser is a LL1 recursive desent parser with backtracking. Left recursion is not supported.`);

            if (thirdWord.value !== this.name) {
                if (!hasExecFunc)
                    console.warn(`Found an rule that is a child of your 'exp' rule, but its third word is not the same as the exp rule.  It also does not have a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);

                return;
            }

            if (hasExecFunc) {
                console.warn(`Found an rule that is a child of your 'exp' rule, but it already has a provided execution function.  Skipping default exp exec function generation for this expression:\n${this.toString()}\nexpression: ${expression.expressionString}`);
                return;
            }

            //Need to get the precedence level by checking which ops this op_n has in it.
            const ops = [];
            this.getOps(exec, secondWord, ops);
            if (ops.length === 0)
                throw new Error(`No operators found for op rule: ${secondWord.string} in expression: ${expression.expressionString} in rule: ${this.name}`);

            const firstOp = ops[0];
            let precedenceLevel = GrammarForge.Expression.operatorTagPrecedence.get(firstOp);
            if (precedenceLevel === undefined)
                throw new Error(`No precedence level found for operator: ${firstOp} in expression: ${expression.expressionString} in rule: ${this.name}`);

            for (let i = 1; i < ops.length; i++) {
                const op = ops[i];
                const opPrecedenceLevel = GrammarForge.Expression.operatorTagPrecedence.get(op);
                if (opPrecedenceLevel === undefined)
                    throw new Error(`No precedence level found for operator: ${op} in expression: ${expression.expressionString} in rule: ${this.name}`);

                if (opPrecedenceLevel !== precedenceLevel)
                    throw new Error(`Mismatched precedence levels found for operators in op rule: ${secondWord.string} in expression: ${expression.expressionString} in rule: ${this.name}.  All operators in an op rule must have the same precedence level.  Found operators: ${ops.join(", ")}`);
            }

            const funcMap = exec.opFunctions[precedenceLevel];
            if (!funcMap)
                throw new Error(`No default op functions found at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

            func = (arr) => {
                const [ exp_n_1, op_n, exp_n ] = arr;
                const left = exp_n_1.exec();
                const right = exp_n.exec();
                const op = op_n.exec();
                const baseFunc = funcMap.get(op);
                if (!baseFunc)
                    throw new Error(`No default op function found for operator: ${op} at precedence level: ${precedenceLevel} in expression: ${expression.expressionString} in rule: ${this.name}`);

                return baseFunc(left, right);
            }
        }

        if (func === null)
            throw new Error(`Fell through the switch trying to make default exp exec function for rule: ${this.name}, expression index: ${expressionIndex}`);

        //console.log(`Auto-generated default exp exec function for rule: ${this.name}, expression index: ${expressionIndex}, expression: ${expression.expressionString}`);
        expression.execFunc = func;
    }

    isOpRule = (exec, word) => {
        if (!(word instanceof GrammarForge.Term))
            return false;

        if (word.type !== "IDENTIFIER")
            throw new Error(`Expected IDENTIFIER, found: ${word.string}`);

        const rule = exec.getRule(word.value);
        if (!rule)
            throw new Error(`No rule found with name: ${word.value}`);

        if (rule.isExpRule !== true)
            throw new Error(`Rule is not an exp rule: ${rule.name}`);

        if (rule.expList.expressions.length === 1) {
            const expression = rule.expList.expressions[0];
            if (expression.words.length !== 1)
                return false;

            if (expression.tag !== null) {
                if (GrammarForge.Expression.operatorTags.has(expression.tag))
                    return true;

                return false;
            }

            const firstWord = expression.words[0];
            if (firstWord instanceof GrammarForge.Term) {
                if (firstWord.type === "IDENTIFIER")
                    return this.isOpRule(exec, firstWord);
            }
            
            return false;
        }
        else {
            //If multiple expressions, they must all be 1 word with an operator tag.
            for (const expression of rule.expList.expressions) {
                if (expression.words.length !== 1)
                    return false;

                if (expression.tag === null)
                    return false;

                if (!GrammarForge.Expression.operatorTags.has(expression.tag))
                    throw new Error(`Op rule expression metadata tag must be one of: ${Array.from(GrammarForge.Expression.operatorTags).join(", ")}.  Found tag: ${expression.tag} in expression: ${expression.expressionString} in rule: ${rule.name}`);
            }

            return true;
        }
    }

    isBaseExpRule = (exec, word) => {
        if (!(word instanceof GrammarForge.Term))
            return false;

        if (word.type !== "IDENTIFIER")
            return false;

        const rule = exec.getRule(word.value);
        if (!rule)
            throw new Error(`No rule found with name: ${word.value}`);

        if (rule.isExpRule !== true)
            throw new Error(`Rule is not an exp rule: ${rule.name}`);

        return !this.isOpRule(exec, word);
    }

    getOps = (exec, word, arr) => {
        if (!(word instanceof GrammarForge.Term))
            throw new Error(`Expected Term, found: ${word.string}`);

        if (word.type === "IDENTIFIER") {
            const rule = exec.getRule(word.value);
            if (!rule)
                throw new Error(`No rule found with name: ${word.value}`);

            for (const expression of rule.expList.expressions) {
                if (expression.words.length !== 1) {
                    throw new Error(`Op rule expressions must have exactly 1 word.  Found expression: ${expression.expressionString} in rule: ${rule.name}`);
                }

                const firstWord = expression.words[0];
                const tag = expression.tag;
                if (tag === null) {
                    this.getOps(exec, firstWord, arr);
                    continue;
                }

                if (expression.metadata.length !== 1) {
                    throw new Error(`Op rule expressions must have exactly 1 metadata tag indicating the operator value.  Found expression: ${expression.expressionString} in rule: ${rule.name}`);
                }

                if (!(firstWord instanceof GrammarForge.Term)) {
                    throw new Error(`Op rule expressions must have a Term as their only word.  Found expression: ${expression.expressionString} in rule: ${rule.name}`);
                }

                if (!GrammarForge.Expression.operatorTags.has(tag)) {
                    throw new Error(`Op rule expression metadata tag must be one of: ${Array.from(GrammarForge.Expression.operatorTags).join(", ")}.  Found tag: ${tag} in expression: ${expression.expressionString} in rule: ${rule.name}`);
                }

                if (firstWord.type === "IDENTIFIER") {
                    const innerRule = exec.getRule(firstWord.value);
                    if (!innerRule)
                        throw new Error(`No rule found with name: ${firstWord.value}`);

                    for (const innerExpression of innerRule.expList.expressions) {
                        if (innerExpression.words.length !== 1) {
                            throw new Error(`Op rule expressions must have exactly 1 word.  Found expression: ${innerExpression.expressionString} in rule: ${innerRule.name}`);
                        }

                        if (innerExpression.tag === null)
                            continue;

                        const innerTag = innerExpression.tag;
                        throw new Error(`Found multiple op tags in nested op rule expressions.  An operator can only have one tag.  Parent rule: ${rule.name}, expression: ${expression.expressionString}, tag: ${tag}, inner rule: ${innerRule.name}, inner expression: ${innerExpression.expressionString}, tag: ${innerTag}`);
                    }
                }

                arr.push(tag);
            }
        }
        else {
            throw new Error(`Not implemented`);
        }
    }

    setKeptWordIndexs = (parser) => {
        return this.expList.setKeptWordIndexs(parser);
    }

    getKeptWordsFromIndexs = (containsOptional = false) => {
        return this.expList.getKeptWordsFromIndexs(containsOptional);
    }

    getChildren = (parser, childrenIndexSet) => {
        this.expList.getChildren(parser, childrenIndexSet);
    }

    // walk = function*() {
    //     yield* this.expList.walk();
    // }

    toString() {
        return `${this.name} ::= ${this.expList.toString(true)}`;
    }
}

GrammarForge.Rule.tags = new Set([
    'sl',
    'stmt',
    'exp',
    'var',
    'block',
    'stmt_exp',
]);
