"use strict";

{
    GrammarForge.stripQuotes = (str) => {
        if (typeof str !== 'string' || str.length <= 2)
            throw new Error(`str: ${str} is not a string or length <= 2.`);

        const first = str[0];
        const last = str[str.length - 1];
        if (first === '\'' && last === '\'' || first === '\'' && last === '\'')
            return str.slice(1, -1);

        throw new Error(`str: ${str} does not have quotes on both sides.`);
    }

    GrammarForge.stringToRegex = (str) => {
        if (typeof str !== 'string' || str.length <= 2)
            throw new Error(`str: ${str} is not a string or length <= 2.`);

        // Remove the starting and ending slashes
        // and extract the flags after the last slash
        const parts = str.match(/^\/(.*?)\/([a-z]*)$/i);
        if (!parts) {
            throw new Error("Invalid regex string");
        }

        const pattern = parts[1]; // "#.*$"
        const flags = parts[2];   // "m"

        const regex = new RegExp(pattern, flags);
        return regex;
    }

    GrammarForge.astStringIndentCount = 0;

    GrammarForge.astString = (ast) => {
        GrammarForge.astStringIndentCount = 0;
        const arr = [];
        ast.toAstString(arr);
        if (GrammarForge.astStringIndentCount !== 0)
            throw new Error("Indent count should be 0 after astString.");

        return arr.join('');
    }

    GrammarForge.printAst = (ast) => {
        let tabs = 0;
        const printNode = (node) => {
            const indent = '\t'.repeat(tabs);
            if (typeof node === 'string' || typeof node === 'number' || typeof node === 'boolean') {
                console.log(`${indent}${node}`);
            }
            else if (Array.isArray(node)) {
                console.log(`${indent}[`);
                tabs++;
                for (const child of node) {
                    printNode(child);
                }
                
                tabs--;
                console.log(`${indent}]`);
            }
            else if (typeof node === 'object' && node !== null) {
                console.log(`${indent}{`);
                tabs++;
                for (const key in node) {
                    if (node.hasOwnProperty(key)) {
                        console.log(`${indent}  ${key}:`);
                        printNode(node[key]);
                    }
                }

                tabs--;
                console.log(`${indent}}`);
            }
        }

        printNode(ast);
    }

    GrammarForge.getTypeStr = (obj) => {
        const type = typeof obj;
        if (type === "object")
            return obj.constructor.name;

        return type;
    }
}
