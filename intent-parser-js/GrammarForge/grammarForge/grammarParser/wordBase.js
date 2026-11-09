"use strict";

GrammarForge.WordBase = class WordBase {
    constructor() {
        if (this.constructor === GrammarForge.WordBase) {
            throw new Error("Abstract class 'WordBase' cannot be instantiated directly.");
        }
    }

    getParseFunc = (parser) => {
        throw new Error("Not implemented");
    }

    getTryParseFunc = (parser) => {
        throw new Error("Not implemented");
    }

    setKeptWordIndexs = (parser) => {
        throw new Error("Not implemented");
    }

    getKeptWordsFromIndexs = (oTypes = null) => {
        throw new Error("Not implemented");
    }

    getChildren = (parser, childrenIndexSet) => {
        throw new Error("Not implemented");
    }

    // walk = function*() {
    //     throw new Error("Not implemented");
    // }

    toString() {
        throw new Error("Not implemented");
    }
}
