"use strict";

GrammarForge.Par = class Par extends GrammarForge.Word {
    constructor(expList) {
        super();
        if (!(expList instanceof GrammarForge.ExpList))
            throw new Error("expList must be an instance of GrammarForge.ExpList");

        this.expList = expList;
        this.parString = this.toString();
    }

    //Returns true if left recursion was checked and not found
    //Throws an error if left recursion is found
    //Returns false if this word was not a match, but is optional
    checkWordForLeftRecursion = (parser, expr, lookAheadSet) => {
        let allChecked = true;
        //Need to check all expressions inside the par in case they allow left recursion.
        for (let i = 0; i < this.expList.expressions.length; i++) {
            const expr = this.expList.expressions[i];
            const checked = expr.checkWordsForLeftRecursion(parser, lookAheadSet);
            if (!checked)
                allChecked = false;
        }

        //If any of the expressions in the Par are completely optional, then the Par is optional, and shouldn't stop looking for left recursion.
        return allChecked;
    }

    getParseFunc = (parser) => {
        return this.expList.getParseFunc(parser);
    }

    getTryParseFunc = (parser) => {
        return this.expList.getTryParseFunc(parser);
    }

    setKeptWordIndexs = (parser) => {
        return this.expList.setKeptWordIndexs(parser);
    }

    getKeptWordsFromIndexs = (oTypes = null) => {
        return this.expList.getKeptWordsFromIndexs(oTypes);
    }

    getChildren = (parser, childrenIndexSet) => {
        this.expList.getChildren(parser, childrenIndexSet);
    }

    // walk = function*() {
    //     yield* this.expList.walk();
    // }

    toString() {
        return `(${this.expList.toString()})`;
    }
}
