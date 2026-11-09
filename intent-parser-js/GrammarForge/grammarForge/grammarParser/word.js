"use strict";

GrammarForge.Word = class Word extends GrammarForge.WordBase {
    constructor() {
        super();
        if (this.constructor === GrammarForge.Word) {
            throw new Error("Abstract class 'Word' cannot be instantiated directly.");
        }
    }
}
