"use strict";

GrammarForge.ProgramTestCase = class ProgramTestCase {
    constructor(programStr, expected) {
        this.programStr = programStr;
        this.expected = expected;
    }
    static fromArray = (arr) => {
        const [programStr, expected] = arr;
        return new ProgramTestCase(programStr, expected);
    }
    test = (gf) => {
        if (gf.execution.logAllTests) {
            console.log(`Testing program:\n${this.programStr}`);
        }

        const ast = gf.parse(this.programStr);
        ProgramTestCase.testAst(gf, ast, this.expected, this.programStr);
    }
    static testAst = (gf, ast, expected, programStr) => {
        gf.execution.testResults.length = 0;

        if (gf.execution.logAllTests) {
            const arrToString = Array.prototype.toString;
            let indentCount = 0;
            Array.prototype.toString = function() {
                if (!this)
                    return '[]';

                indentCount++;
                const childIndent = ' '.repeat(indentCount);
                const innerStr = this.map(x => `${childIndent}${x}`).join(',\n');
                indentCount--;
                return `Array: [\n${innerStr}\n${' '.repeat(indentCount)}]`;
            }

            // const downloadString = (text) => {
            //     const blob = new Blob([text], { type: "text/plain" });
            //     const a = document.createElement("a");
            //     a.href = URL.createObjectURL(blob);
            //     a.download = "log.txt";
            //     a.click();
            // }

            const astText = `${ast}`;
            Array.prototype.toString = arrToString;
            console.log(astText);
            //downloadString(astText);
        }
        
        gf.exec(ast);
        if (gf.execution.logAllTests) {
            console.log(`Expected results: ${expected}`);
            console.log(`Actual results:   ${gf.execution.testResults}`);
        }

        if (gf.execution.testResults.length !== expected.length) {
            if (!gf.execution.logAllTests) {
                console.log(programStr);
            }

            console.error(`Test failed. Expected ${expected.length} results, got ${gf.execution.testResults.length}`);
            console.error(`Expected: ${expected}`);
            console.error(`Got: ${gf.execution.testResults}`);
        }
        else {
            let printedFirst = false;
            for (let i = 0; i < expected.length; i++) {
                const result = gf.execution.testResults[i];
                if (result != expected[i]) {
                    if (!printedFirst) {
                        printedFirst = true;
                        if (!gf.execution.logAllTests) {
                            console.log(programStr);
                        }
                    }
                    
                    console.error(`Test failed at result ${i}. Expected: ${expected[i]}, got: ${result}`);
                    break;
                }
            }
        }

        gf.execution.testResults.length = 0;
    }
}
