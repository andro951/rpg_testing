"use strict";

(() => {
    //Make arrays print as:
    // [ item1, item2, ... ]
    //instead of:
    // item1,item2,...
    Array.prototype.toString = function() {
        return `[ ${this ? this.join(", ") : ""} ]`;
    }
})();

/*
GrammarForge is a recursive decent parser generator with backtracking.

How to write a grammar for GrammarForge:
Start with the base rule that should always be the highest level rule in the Abstract Syntax Tree (AST).

Defining Rules:
RuleName : RuleDefinition
RuleDefinitions are one or more Expressions separated by '|' to indicate alternatives.
Expressions are one or more Words separated by whitespace.
Words are Symbols, Tokens, names of Rules, or grouped Expressions in parentheses.
Example of a Rule Definition:
    func : NAME LPAREN expr... RPAREN
    Rule name: 'func'
    1 Rule expressions: [ "NAME LPAREN expr... RPAREN" ]
    4 Expression words: [ "NAME", "LPAREN", "expr...", "RPAREN" ]
    The 3rd word is an Expression list seperated by commas which can contain multiple words.

In the rule definition, the collon can be ':', ':=' or '::='.
Symbols used in rule definitions:
    '(', ')', '*', '+', '?', '|', '{', '}', '...', ':', ':=', '::='
To use these symbols in your grammar, you must use a token definition instead and use the token in your grammar.




: indicates a rule definition.  Example:
    ruleName : ruleDefinition

| indicates an alternative.  Example:
    ruleName : ruleDefinition1
             | ruleDefinition2
(symbol)? indicates that symbol is optional.  Example:
    ruleName : (symbol)?

(symbol)* indicates that symbol can appear zero or more times.  Example:
    ruleName : (symbol)*

(symbol)+ indicates that symbol can appear one or more times.  Example:
    ruleName : (symbol)+

(symbol)... indicates that symbol is an expression list separated by commas.  Example:
    ruleName : (symbol)...

Uppercase names are tokens (terminal symbols).
Lowercase names are rules (non-terminal symbols).

A token definition looks like this:
    TOKEN_NAME : regex

Tokens can have a tag to provide additional information.  They can optionally have parentheses around the tag.  Example:
To have a token ignored by the lexer, put (IGNORE) after the token definition.  Example:
    COMMENT : \#.*\m (IGNORE)
To show that a type needs to be parsed, put the tag after the regex.  Example:
    MY_INT : /\d+/ int

Supported tags:
int - integer
float - floating point number
string - string
IGNORE - ignore this token (do not include it in the token stream)

Default tokens always added:
COMMA, /,/ is added at the end to support expression lists. (Added so that delimited lists with ... have a default delimiter.)
WHITESPACE, /\s+/ (IGNORE) is added at the end to ignore whitespace.
SYMBOL, /[^a-zA-Z0-9_\s:|()*+?'"\`;]/ is added at the end to match most symbols not used in grammar definitions. (You can use 
    these directly in your grammer instead of a token if desired.)
UNKNOWN, /./ is added at the very end and throws an error if no other token matches.
*/

const GrammarForge = class GrammarForge {
    constructor(grammar, functions = null, tokenDefinitions = null) {
        if (typeof grammar !== 'string')
            throw new Error("Grammar must be a string.");

        if (functions === null)
            functions = [];

        if (!Array.isArray(functions) || !functions.every(f => f instanceof GrammarForge.RuleFunctionDefinition))
            throw new Error("Functions must be an array of RuleFunctionDefinition instances or null.");

        if (tokenDefinitions !== null) {
            if (!Array.isArray(tokenDefinitions) || !tokenDefinitions.every(td => td instanceof GrammarForge.TokenDefinition))
                throw new Error("Token definitions must be an array of GrammarForge.TokenDefinition instances or null.");
        }

        this.grammar = grammar;
        this.functions = functions;
        this.argTokenDefinitions = tokenDefinitions;
        this.allowFunctionRecursion = true;
        this.setup();
    }

    static makeFullAST = false;

    setup = () => {
        this.processGrammar();
        this.createLexer();
        this.createParser();
        this.createExec();
    }

    processGrammar = () => {
        let grammarTokens = GrammarForge.GrammarLexer.tokenize(this.grammar);
        const { rules, tokenDefinitions, expressions, expressionByRuleNameThenExpressionStringLookup } = GrammarForge.GrammarParser.parse(grammarTokens);

        this.rules = rules;
        this.expressions = expressions;
        this.expressionByRuleNameThenExpressionStringLookup = expressionByRuleNameThenExpressionStringLookup;

        if (tokenDefinitions.length > 0) {
            if (this.argTokenDefinitions && this.argTokenDefinitions.length > 0) {
                throw new Error("Token definitions provided in both grammar and constructor.  Only one allowed.");
            }

            this.tokenDefinitions = tokenDefinitions;
        }
        else {
            this.tokenDefinitions = this.argTokenDefinitions;
        }
        
        // console.log("Parsed Rules:");
        // console.log(GrammarForge.GrammarParser.rulesToString());
        // console.log("\nParsed Token Definitions:");
        // console.log(GrammarForge.GrammarParser.tokenDefinitionsToString());
    }

    createLexer = () => {
        this.lexer = new GrammarForge.Lexer(this.tokenDefinitions);
    }

    createParser = () => {
        this.parser = new GrammarForge.Parser(this.rules, this.lexer);
    }

    createExec = () => {
        this.execution = new GrammarForge.Exec(this, this.expressions, this.expressionByRuleNameThenExpressionStringLookup, this.functions);
    }

    parse = (str) => {
        return this.parser.parse(str);
    }

    exec = (ast, variables = null, variableGetters = null, printToConsole = true) => {
        return this.execution.exec(ast, variables, variableGetters, printToConsole);
    }

    replaceOpFunction = (opTag, func) => {
        if (typeof opTag !== 'string')
            throw new Error(`Operator must be a string.`);

        if (typeof func !== 'function')
            throw new Error(`Function must be a function.`);

        const precedence = GrammarForge.Expression.operatorTagPrecedence.get(opTag);
        if (precedence === undefined)
            throw new Error(`Unknown operator: ${opTag}`);

        const op = GrammarForge.Expression.operatorTagToOperator.get(opTag);
        if (op === undefined)
            throw new Error(`Operator tag ${opTag} does not correspond to a valid operator.`);

        if (!this.execution.opFunctions[precedence].has(op))
            throw new Error(`Operator ${op} not defined in precedence level ${precedence}`);

        this.execution.opFunctions[precedence].set(op, func);
    }

    runTests = (tests, testEnvironment) => {
        this.execution.testMode = true;
        console.log(`Running ${tests.length} ${testEnvironment} tests...`);

        for (const testCase of tests) {
            testCase.test(this);
        }

        console.log(`All ${testEnvironment} tests completed.`);
        this.execution.testMode = false;
    }

    setParseTokenFunction = (tokenTag, func) => {
        this.parser.setParseTokenFunction(tokenTag, func);
    }

    disableRecursion = () => {
        this.allowFunctionRecursion = false;
        this.execution.disableRecursion();
    }
};

GrammarForge.debuggingFunctions = false;
