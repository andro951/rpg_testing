"use strict";

GrammarForge.FlowControlID = {
    NONE: 0,
    NORMAL: 1,
    BREAK: 2,
    CONTINUE: 3,
    RETURN: 4,
    RETURN_NO_VALUE: 5,
    COUNT: 6
}

GrammarForge.FlowControl = class FlowControl {
    constructor(type) {
        if (!type)
            throw new Error("type is required");

        if (typeof type !== 'number' || !Number.isInteger(type))
            throw new Error("type must be an integer");
        
        if (type <= GrammarForge.FlowControlID.NONE || type >= GrammarForge.FlowControlID.COUNT)
            throw new Error("Invalid type");

        this.type = type;
    }

    toString() {
        return `${this.type}`;
    }
}

GrammarForge.NormalControl = class NormalControl extends GrammarForge.FlowControl {
    constructor() {
        super(GrammarForge.FlowControlID.NORMAL);
    }
}

GrammarForge.NORMAL_CONTROL = new GrammarForge.NormalControl();

GrammarForge.BreakControl = class BreakControl extends GrammarForge.FlowControl {
    constructor() {
        super(GrammarForge.FlowControlID.BREAK);
    }
}

GrammarForge.BREAK_CONTROL = new GrammarForge.BreakControl();

GrammarForge.ContinueControl = class ContinueControl extends GrammarForge.FlowControl {
    constructor() {
        super(GrammarForge.FlowControlID.CONTINUE);
    }
}

GrammarForge.CONTINUE_CONTROL = new GrammarForge.ContinueControl();

GrammarForge.ReturnControl = class ReturnControl extends GrammarForge.FlowControl {
    constructor(value) {
        super(GrammarForge.FlowControlID.RETURN);
        this.value = value;
    }
}

GrammarForge.ReturnNoValueControl = class ReturnNoValueControl extends GrammarForge.FlowControl {
    constructor() {
        super(GrammarForge.FlowControlID.RETURN_NO_VALUE);
    }
}

GrammarForge.RETURN_NO_VALUE_CONTROL = new GrammarForge.ReturnNoValueControl();
