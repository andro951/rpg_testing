"use strict";

GrammarForge.TokenDefinition = class TokenDefinition {
    constructor(type, regex, tag = null) {
        if (!type)
            throw new Error("type is required");

        if (!regex)
            throw new Error("regex is required");

        if (tag !== null && typeof tag !== 'string')
            throw new Error("tag must be a string or null");

        this.type = type;
        this.regex = regex;
        if (!(regex instanceof RegExp))
            throw new Error(`Invalid regex for token ${type}: ${regex}`);
            
        this.tag = tag;
    }

    toString() {
        return `${this.type} ::= ${this.regex}${this.tag ? ` (${this.tag})` : ''}`;
    }
}
