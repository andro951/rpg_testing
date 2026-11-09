"use strict";

GrammarForge.Token = class Token {
    constructor(type, value) {
        this.type = type;
        this.value = value;
    }

    toString() {
        return `${this.value}{${this.type}}`;
    }
}
