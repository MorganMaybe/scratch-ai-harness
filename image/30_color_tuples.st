"Scratch AI Harness - color literals in block tuples.

The model emits colors as '#rrggbb' strings.  The bridge compiles them to a
safe marker array:

    #(#color 255 0 0)

The image must turn that marker into a real Squeak Color object before the
native tuple builder sees it; touchingColor:, color:sees: and penColor:
all expect Color values, not strings or integers.

Load after 15_reply_context.st and 28_sprites_stage.st."

(Smalltalk at: #AIChangeSetApplier) class compile: 'resolveColorTuples: aValue
    (aValue isKindOf: Array)
        ifFalse: [^ aValue].
    ((aValue size = 4) and: [(aValue at: 1) = #color])
        ifTrue: [
            ^ Color
                r: (aValue at: 2) / 255.0
                g: (aValue at: 3) / 255.0
                b: (aValue at: 4) / 255.0].
    ^ aValue collect: [:item | self resolveColorTuples: item]' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'addScript: id target: targetName tuples: tupleList
    | target stack resolved |
    resolved := self resolveColorTuples: tupleList.
    target := self targetNamed: targetName.
    target ifNil: [
        self reportProblem: ''Unknown target: '', targetName asString.
        ^ nil].
    stack := target stackFromTupleList: resolved receiver: target.
    target addStack: stack.
    self scripts at: id put: stack.
    self recordHashFor: id tuples: resolved.
    ^ stack' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'replaceScript: id target: targetName tuples: tupleList
    | target stack old resolved |
    resolved := self resolveColorTuples: tupleList.
    old := self scripts at: id ifAbsent: [nil].
    old ifNil: [
        self reportProblem: ''Cannot replace unknown script '', id asString.
        ^ nil].
    target := self targetNamed: targetName.
    target ifNil: [
        self reportProblem: ''Unknown target: '', targetName asString.
        ^ nil].
    stack := target stackFromTupleList: resolved receiver: target.
    old delete.
    target addStack: stack.
    self scripts at: id put: stack.
    self recordHashFor: id tuples: resolved.
    ^ stack' classified: 'applying'.
