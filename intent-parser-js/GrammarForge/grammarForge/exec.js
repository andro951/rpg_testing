"use strict";

{
    GrammarForge.Exec = class {
        constructor(grammarForge, expressions, expressionByRuleNameThenExpressionStringLookup, functions = null) {
            this.gf = grammarForge;
            this.parser = this.gf.parser;
            this.parser.exec = this;
            this.expressions = expressions;
            this.expressionByRuleNameThenExpressionStringLookup = expressionByRuleNameThenExpressionStringLookup;
            this.getRule = this.parser.getRule;
            this.ruleTagLookup = this.parser.ruleTagLookup;
            this.stmt_rule = this.ruleTagLookup.get("stmt");
            this.metaExpressionLookup = this.parser.metaExpressionLookup;
            this.testMode = false;
            this.logAllTests = false;
            this.testResults = [];
            this.printArr = [];
            if (!this.gf.allowFunctionRecursion)
                this.disableRecursion();
            
            this.setup(functions);
        }

        setup = (functions) => {
            this.ruleIndexLookup = this.parser.ruleIndexLookup;

            this.makeDefaultExecFunctions();
            this.makeOperatorTokenTagMap();
            this.createExecFunctions(functions);

            for (let i = 0; i < this.parser.rules.length; i++) {
                const rule = this.parser.rules[i];
                rule.checkMakeDefaultExecFunctions(this);
            }
        }

        disableRecursion() {
            this.functionsOnStack = new Set();
        }

        markExpressionsInWordAsNotAutomaticallyGenerated = (word) => {
            if (word instanceof GrammarForge.Term) {
                return;
            }
            else if (word instanceof GrammarForge.Par) {
                for (const exp of word.expList.expressions) {
                    this.markAsNotAutomaticallyGenerated(exp);
                }
            }
            else if (word instanceof GrammarForge.QWord) {
                this.markExpressionsInWordAsNotAutomaticallyGenerated(word.word);
                if (word.delimiterWord)
                    this.markExpressionsInWordAsNotAutomaticallyGenerated(word.delimiterWord);
            }
            else {
                throw new Error(`Unexpected word type in markExpressionsInWordAsAutomaticallyGenerated: ${word.constructor.name}`);
            }
        }

        markAsNotAutomaticallyGenerated = (expression) => {
            expression.automaticallyGeneratedFunc = false;
            for (const word of expression.words) {
                this.markExpressionsInWordAsNotAutomaticallyGenerated(word);
            }
        }

        createExecFunctions = (functions) => {
            //Populate execFunctions from user functions
            if (functions) {
                for (const funcDef of functions) {
                    if (!(funcDef instanceof GrammarForge.RuleFunctionDefinition))
                        throw new Error(`Functions array must contain only RuleFunctionDefinition instances.  Found: ${funcDef.constructor.name}`);

                    const ruleName = funcDef.ruleName;
                    const ruleExpressionMap = this.expressionByRuleNameThenExpressionStringLookup.get(ruleName);
                    if (ruleExpressionMap) {
                        const expressionString = funcDef.expressionString;
                        const expression = ruleExpressionMap.get(expressionString);
                        if (expression === undefined)
                            throw new Error(`No expression found with string: ${expressionString} in rule: ${ruleName}`);

                        expression.execFunc = funcDef.func;
                        this.markAsNotAutomaticallyGenerated(expression);
                    }
                    else {
                        throw new Error(`No rule found with name: ${ruleName} for user-defined exec function.`);
                    }
                }
            }

            //Simple default functions like sl (statement list) are generated here because it doesn't require an expression tag.  
            //  Others are created by the rule objects.
            const tryGetInnerWord = (word) => {
                if (word instanceof GrammarForge.Term)
                    return word;

                if (word instanceof GrammarForge.Par) {
                    const expList = word.expList;
                    if (expList.expressions.length === 1) {
                        const expr = expList.expressions[0];
                        if (expr.words.length === 1)
                            return tryGetInnerWord(expr.words[0]);
                    }
                    else {
                        return null;
                    }
                }
            }

            //sl (statement list)
            if (this.stmt_rule !== undefined) {
                let foundCount = 0;
                let found = false;
                for (let i = 0; i < this.parser.rules.length; i++) {
                    foundCount = 0;
                    const rule = this.parser.rules[i];
                    for (let j = 0; j < rule.expList.expressions.length; j++) {
                        const expr = rule.expList.expressions[j];
                        const keptWords = expr.getKeptWordsFromIndexs();
                        if (keptWords.length === 1) {
                            const exprKeptWordIndexes = expr.keptWordIndexes;
                            const keptWordIndex = exprKeptWordIndexes[0];
                            const word = expr.words[keptWordIndex];
                            if (word instanceof GrammarForge.QWord && (word.oType === "PLUS" || word.oType === "STAR")) {
                                const keptWordWord = keptWords[0];
                                if (!(keptWordWord instanceof GrammarForge.Term))
                                    continue;

                                if (keptWordWord.type !== "IDENTIFIER" || keptWordWord.value !== this.stmt_rule.name)
                                    continue;

                                foundCount++;
                            }
                        }
                    }

                    if (foundCount > 0) {
                        if (foundCount !== rule.expList.expressions.length)
                            throw new Error(`Attempted to automatically determine a statement list rule, but a rule partially succeded: ${rule.toString()}`);

                        if (this.parser.ruleTagLookup.has('sl') && this.parser.ruleTagLookup.get('sl') !== rule || found)
                            throw new Error(`Multiple rules found that look like statement lists.  Only one rule can be tagged as 'sl'.  Conflicting rules:\n${rule.toString()}, ${this.parser.ruleTagLookup.get('sl').toString()}`);

                        this.parser.ruleTagLookup.set('sl', rule);
                        if (rule.tag !== null)
                            throw new Error(`Tried to tag rule as 'sl', but it already has a tag: ${rule.tag}, rule: ${rule.toString()}`);

                        rule.tag = 'sl';
                        this.slRule = rule;
                        found = true;
                        //console.log(`Automatically determined statement list rule:\n${rule.toString()}`);
                    }
                }

                if (!found)
                    console.warn(`A rule was tagged as stmt:\n${this.stmt_rule.toString()}\nbut no rules were recognized as a statement list.  Statement lists should only look like (stmt)* or (stmt)+`);
            }

            //stmt_exp in a stmt
            const stmt_exp_rule = this.ruleTagLookup.get('stmt_exp');
            if (this.stmt_rule !== undefined && stmt_exp_rule !== undefined) {
                let found = false;
                for (let j = 0; j < this.stmt_rule.expList.expressions.length; j++) {
                    const expr = this.stmt_rule.expList.expressions[j];
                    const keptWords = expr.getKeptWordsFromIndexs();
                    if (keptWords.length === 1) {
                        const word = keptWords[0];
                        if (word instanceof GrammarForge.Term && word.type === "IDENTIFIER") {
                            const rule = this.getRule(word.value);
                            if (!rule)
                                throw new Error(`No rule found for non-terminal: ${word.value}`);

                            if (rule !== stmt_exp_rule)
                                continue;

                            found = true;
                            if (expr.execFunc !== null) {
                                console.warn(`A rule was tagged as stmt:\n${this.stmt_rule.toString()}\nbut the expression that looks like a stmt_exp statement already has a user-defined exec function.  Skipping default stmt_exp statement function generation for this expression:\n${expr.expressionString}`);
                                continue;
                            }

                            const func = this.defaultExecFunctions.get("stmt_exp");
                            expr.execFunc = (stmt_exp) => func(stmt_exp);
                        }
                    }
                }

                if (!found)
                    throw new Error(`A rule was tagged as stmt:\n${this.stmt_rule.toString()}\nand a rule was tagged as stmt_exp:\n${stmt_exp_rule.toString()}\nbut no expressions in the stmt rule were recognized as a stmt_exp statement.  There should be an expression on the stmt rule that only contains only the rule name of the rule tagged stmt_exp.`);
            }

            Object.freeze(this.ruleTagLookup);
        }

        tryPrintStoredLogsToConsole = () => {
            if (this.printArr.length > 0) {
                console.log(this.printArr.join("\n"));
                this.printArr.length = 0;
            }
        }

        exec = (ast, variables = null, variableGetters = null, printToConsole = true) => {
            if (variables === null) {
                variables = new Map();
            }
            else if (!(variables instanceof Map)) {
                throw new Error("Variables parameter must be a Map or null.");
            }

            if (variableGetters !== null) {
                if (!(variableGetters instanceof Map))
                    throw new Error("Variable getters parameter must be a Map or null.");
            }

            this.variables = [ variables ];
            this.variableGetters = variableGetters;
            this.printArr.length = 0;
            const result = this.execute(ast);
            if (printToConsole)
                this.tryPrintStoredLogsToConsole();

            this.variables = null;
            this.variableGetters = null;
            return result;
        }

        execute = (ast) => {
            if (Array.isArray(ast)) {
                throw new Error("AST node cannot be an array.");
            }

            if (!(ast instanceof GrammarForge.AstNode))
                throw new Error(`Expected AST node to be a RuleNode, found ${ast.constructor.name}`);

            if (!this.variables)
                throw new Error("No variables context available for execution.  Call exec() to execute AST.");

            if (ast.empty)
                return GrammarForge.NORMAL_CONTROL;

            return ast.exec();
        }

        token = (ast, requiredTokenType) => {
            if (ast.length !== 3)
                throw new Error(`TOKEN node must have exactly two children.`);

            const [ type, tokenType, value ] = ast;
            if (type !== 'TOKEN')
                throw new Error(`Expected TOKEN node, found ${type}`);

            if (tokenType !== requiredTokenType)
                throw new Error(`Expected token type ${requiredTokenType}, found ${tokenType}`);

            return value;
        }

        check_token = (ast, requiredTokenType) => {
            if (ast.length !== 3)
                throw new Error(`TOKEN node must have exactly 3 children.`);

            const [ type, tokenType, ] = ast;
            if (type !== 'TOKEN')
                throw new Error(`Expected TOKEN node, found ${type}`);

            if (tokenType !== requiredTokenType)
                throw new Error(`Expected token type ${requiredTokenType}, found ${tokenType}`);
        }

        check_symbol = (ast, requredSymbol) => {
            if (ast.length !== 2)
                throw new Error(`SYMBOL node must have exactly 2 children.`);

            const [ type, symbol ] = ast;
            if (type !== 'SYMBOL')
                throw new Error(`Expected SYMBOL node, found ${type}`);

            if (symbol !== requredSymbol)
                throw new Error(`Expected symbol ${requredSymbol}, found ${symbol}`);
        }

        check_type = (ast, expectedType) => {
            const type = ast[0];
            if (type !== expectedType)
                throw new Error(`Expected ${expectedType} node, found ${type}`);
        }

        check_length = (ast, expectedLength) => {
            if (ast.length === expectedLength)
                return;

            throw new Error(`Expected ${expectedLength} children, found ${ast.length}`);
        }

        check_optional = (ast) => {
            if (!Array.isArray(ast))
                throw new Error(`Expected optional node to be an array.`);
        }

        check_required = (ast) => {
            if (!Array.isArray(ast))
                throw new Error(`Expected required node to be an array.`);

            if (ast.length === 0)
                throw new Error(`Expected required node to have at least one child.`);
        }

        push_block_scope = () => {
            this.variables.push(new Map());
        }

        pop_block_scope = () => {
            if (this.variables.length === 1)
                throw new Error("Cannot pop global scope.");

            this.variables.pop();
        }

        declare_variable_default_value = (name) => {
            this.declare_variable(name, null);
        }

        declare_variable = (name, val) => {
            if (this.variableGetters && this.variableGetters.has(name)) {
                throw new Error(`${name} is reserved for a global value.  It cannot be used as a variable name.`);
            }

            const variables = this.variables;

            for (let i = variables.length - 1; i >= 0; i--) {
                const scope = variables[i];
                if (scope.has(name))
                    throw new Error(`Variable ${name} is already declared.  Variable shadowing/re-declaration is not allowed.`);
            }

            variables[variables.length - 1].set(name, val);
            if (GrammarForge.debuggingFunctions) {
                console.log(`let ${name} = ${val}`);
            }
        }

        set_variable = (name, val) => {
            if (this.variableGetters && this.variableGetters.has(name)) {
                throw new Error(`${name} is reserved for a global value.  It cannot be edited.`);
            }

            const variables = this.variables;

            for (let i = variables.length - 1; i >= 0; i--) {
                const scope = variables[i];
                if (scope.has(name)) {
                    scope.set(name, val);
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`${name} = ${val}`);
                    }

                    return;
                }
            }

            throw new Error(`Tried to set undefined variable: ${name}`);
        }

        try_declare_then_set_variable = (name, val) => {
            if (this.variableGetters && this.variableGetters.has(name)) {
                throw new Error(`${name} is reserved for a global value.  It cannot be edited.`);
            }

            const variables = this.variables;

            let found = false;
            for (let i = variables.length - 1; i >= 0; i--) {
                const scope = variables[i];
                if (scope.has(name)) {
                    found = true;
                    scope.set(name, val);
                }
            }

            if (!found) {
                variables[variables.length - 1].set(name, val);
            }

            if (GrammarForge.debuggingFunctions) {
                console.log(`${name} = ${val}`);
            }
        }

        get_variable = (name) => {
            if (this.variableGetters && this.variableGetters.has(name)) {
                return this.variableGetters.get(name)();
            }

            const variables = this.variables;
            for (let i = variables.length - 1; i >= 0; i--) {
                const scope = variables[i];
                if (scope.has(name)) {
                    return scope.get(name);
                }
            }

            throw new Error(`Tried to access undefined variable: ${name}`);
        }

        makeDefaultExecFunctions = () => {
            const execution = this;
            const declare_variable = (...args) => execution.declare_variable(...args);
            const declare_variable_default_value = (...args) => execution.declare_variable_default_value(...args);
            const set_variable = (...args) => execution.set_variable(...args);
            const get_variable = (...args) => execution.get_variable(...args);
            const try_declare_then_set_variable = (...args) => execution.try_declare_then_set_variable(...args);
            this.defaultExecFunctions = new Map([
                ['sl', (stmt_list) => {
                    for (const stmt of stmt_list) {
                        const result = stmt.exec();
                        if (result.type === undefined)
                            throw new Error(`Expected statement execution result to have a type property.  Found: ${result}`);

                        if (result.type !== GrammarForge.FlowControlID.NORMAL)
                            return result;
                    }

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['stmt', (stmt) => {
                    return stmt.exec();
                }],
                ['stmt_exp', (exp) => {
                    exp.exec();
                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['while', (exp, stmt) => {
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`while start`);
                    }
                    
                    while (exp.exec()) {
                        const result = stmt.exec();
                        let breakWhile = false;
                        switch (result.type) {
                            case GrammarForge.FlowControlID.BREAK:
                                breakWhile = true;
                                break;
                            case GrammarForge.FlowControlID.CONTINUE:
                                continue;
                            case GrammarForge.FlowControlID.NORMAL:
                                break;
                            default:
                                return result;
                        }

                        if (breakWhile)
                            break;
                    }

                    
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`while end`);
                    }

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['foreach', (var_, exp, stmt) => {
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`foreach start`);
                    }

                    const iterable = exp.exec();
                    if (!iterable || typeof iterable[Symbol.iterator] !== 'function') {
                        throw new Error(`Foreach expression did not return an iterable.`);
                    }

                    execution.push_block_scope();
                    const variableName = var_.exec();
                    declare_variable_default_value(variableName);
                    for (const item of iterable) {
                        set_variable(variableName, item);
                        const result = stmt.exec();
                        let breakForeach = false;
                        switch (result.type) {
                            case GrammarForge.FlowControlID.BREAK:
                                breakForeach = true;
                                break;
                            case GrammarForge.FlowControlID.CONTINUE:
                                continue;
                            case GrammarForge.FlowControlID.NORMAL:
                                break;
                            default:
                                return result;
                        }

                        if (breakForeach)
                            break;
                    }

                    execution.pop_block_scope();
                    
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`foreach end`);
                    }

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['declare', (var_, exp) => {
                    const v = var_.exec();
                    const value = exp.exec();
                    declare_variable(v, value);

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['declare no_value', (var_) => {
                    const v = var_.exec();
                    declare_variable_default_value(v);

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['assign', (var_, exp) => {
                    const v = var_.exec();
                    const value = exp.exec();
                    set_variable(v, value);

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['assign no_declare', (var_, exp) => {//Used if {assign no_declare} tag is set
                    const v = var_.exec();
                    const value = exp.exec();
                    try_declare_then_set_variable(v, value);

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['get', (var_) => {
                    const v = var_.exec();
                    return get_variable(v);
                }],
                ['post_inc', (var_) => {
                    const v = var_.exec();
                    const oldValue = get_variable(v);
                    set_variable(v, oldValue + 1);
                    return oldValue;
                }],
                ['post_dec', (var_) => {
                    const v = var_.exec();
                    const oldValue = get_variable(v);
                    set_variable(v, oldValue - 1);
                    return oldValue;
                }],
                ['pre_inc', (var_) => {
                    const v = var_.exec();
                    const value = get_variable(v) + 1;
                    set_variable(v, value);
                    return value;
                }],
                ['pre_dec', (var_) => {
                    const v = var_.exec();
                    const value = get_variable(v) - 1;
                    set_variable(v, value);
                    return value;
                }],
                ['block', (stmt_list) => {
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`block start`);
                    }

                    execution.push_block_scope();
                    const result = stmt_list.exec();
                    execution.pop_block_scope();

                    if (GrammarForge.debuggingFunctions) {
                        console.log(`block end`);
                    }
                    
                    return result;
                }],
                ['par', (exp) => {
                    return exp.exec();
                }],
                ['break', () => {
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`BREAK`);
                    }

                    return GrammarForge.BREAK_CONTROL;
                }],
                ['continue', () => {
                    if (GrammarForge.debuggingFunctions) {
                        console.log(`CONTINUE`);
                    }

                    return GrammarForge.CONTINUE_CONTROL;
                }],
                ['if', (exp, stmt, else_stmt) => {
                    if (exp.exec()) {
                        return stmt.exec();
                    }
                    else {
                        if (else_stmt.empty) {
                            return GrammarForge.NORMAL_CONTROL;
                        }
                        else {
                            return else_stmt.exec();
                        }
                    }
                }],
                ['ternary', (exp, optional) => {
                    return exp.exec() ? optional[0].exec() : optional[1].exec();
                }],
                ['print', (exp) => {
                    const val = exp.empty ? '' : exp.exec();
                    if (execution.testMode) {
                        execution.testResults.push(val);
                        if (GrammarForge.debuggingFunctions) {
                            execution.printArr.push(`print: ${val}`);
                        }
                    }
                    else {
                        execution.printArr.push(String(val));
                    }

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['return', (exp) => {
                    const value = exp.exec();
                    return new GrammarForge.ReturnControl(value);
                }],
                ['return optional', (exp) => {
                    if (exp.empty)
                        return GrammarForge.RETURN_NO_VALUE_CONTROL;

                    const value = exp.exec();
                    return new GrammarForge.ReturnControl(value);
                }],
                ['func_declare', (var_, parametersArr, block) => {
                    const v = var_.exec();
                    
                    const parameters = parametersArr.map((param) => param.exec());

                    const val = new GrammarForge.FunctionDeclaration(
                        v,
                        parameters,
                        block,
                        execution,
                        execution.gf.allowFunctionRecursion
                    );

                    try_declare_then_set_variable(v, val);

                    if (GrammarForge.debuggingFunctions) {
                        console.log(`let ${v} = ${val}`);
                    }

                    return GrammarForge.NORMAL_CONTROL;
                }],
                ['func_call', (var_, argsArr) => {
                    const v = var_.exec();
                    if (execution.functionsOnStack) {
                        if (execution.functionsOnStack.has(v))
                            throw new Error(`Recursion detected. ${v} was called while another instance of ${v} is being executed. Recursion is not allowed.`);

                        execution.functionsOnStack.add(v);
                    }

                    const func = execution.get_variable(v);
                    if (!(func instanceof GrammarForge.FunctionDeclaration))
                        throw new Error(`Tried to call vairable as a function, but it is not a function: ${v}, type: ${type}, value: ${func}`);

                    let args = argsArr.map(arg => arg.exec());

                    const result = func.call(args);

                    if (execution.functionsOnStack)
                        execution.functionsOnStack.delete(v);

                    if (result instanceof GrammarForge.ReturnControl) {
                        return result.value;
                    }
                    else if (result instanceof GrammarForge.ReturnNoValueControl || result instanceof GrammarForge.NormalControl) {
                        return undefined;
                    }

                    throw new Error(`Function ${v} did not return a value properly.`);
                }],
            ]);

            this.opFunctions = [
                new Map([
                    ['||', (left, right) => left || right],
                ]),
                new Map([
                    ['&&', (left, right) => left && right],
                ]),
                new Map([
                    ['==', (left, right) => left === right],
                    ['!=', (left, right) => left !== right],
                    ['<', (left, right) => left < right],
                    ['<=', (left, right) => left <= right],
                    ['>', (left, right) => left > right],
                    ['>=', (left, right) => left >= right],
                ]),
                new Map([
                    ['+', (left, right) => left + right],
                    ['-', (left, right) => left - right],
                ]),
                new Map([
                    ['*', (left, right) => left * right],
                    ['/', (left, right) => left / right],
                    ['%', (left, right) => left % right],
                ]),
                new Map([
                    ['!', (value) => !value],
                    ['-', (value) => -value],
                    ['+', (value) => +value],
                ]),
                new Map([
                    ['^', (base, exponent) => base ** exponent],
                ]),
            ];

            Object.freeze(this.defaultExecFunctions);
        }

        makeOperatorTokenTagMap = () => {
            this.operatorTokenTagMap = [];//array of maps <token, tag>
            for (let i = 0; i < 8; i++) {
                this.operatorTokenTagMap.push(new Map());
            }
            
            for (const [ key, ruleExprArr ] of this.metaExpressionLookup) {
                if (!GrammarForge.Expression.operatorTags.has(key))
                    continue;

                for (const [ rule, expression ] of ruleExprArr) {
                    const tag = expression.tag;
                    if (tag === null)
                        return;

                    if (tag !== key)
                        throw new Error(`Mismatched operator tag.  Expected: ${key}, found: ${tag} in expression: ${expression.expressionString} in rule: ${rule.name}`);

                    if (expression.words.length !== 1)
                        throw new Error(`Expression tagged as ${tag} must contain exactly one operator token.  Expression: ${expression.expressionString} in rule: ${this.name}`);

                    const word = expression.words[0];
                    if (!(word instanceof GrammarForge.Term))
                        throw new Error(`Expression tagged as ${tag} must contain exactly one operator token.  Expression: ${expression.expressionString} in rule: ${this.name}`);

                    if (word.type !== 'TOKEN' && word.type !== 'MATH_SYMBOL' && word.type !== 'TAG_OPEN' && word.type !== 'TAG_CLOSE' && word.type !== 'PLUS' && word.type !== 'STAR')
                        throw new Error(`Expression tagged as ${tag} must contain exactly one operator token.  Expression: ${expression.expressionString} in rule: ${this.name}`);

                    if (!GrammarForge.Expression.operatorTagPrecedence.has(tag))
                        throw new Error(`Missing operator tag precedence for tag: ${tag}`);

                    const precedence = GrammarForge.Expression.operatorTagPrecedence.get(tag);
                    const tagMap = this.operatorTokenTagMap[precedence];
                    if (tagMap.has(word.value))
                        throw new Error(`Duplicate operator token for tag ${tag}: ${word.value}`);

                    tagMap.set(word.value, tag);
                }
            }

            Object.freeze(this.operatorTokenTagMap);
        }
    }
}
