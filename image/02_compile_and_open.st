((Smalltalk includesKey: #AIHarnessPaneMorph) and: [Smalltalk includesKey: #AIHarness])
    ifFalse: [
        DialogBoxMorph inform: 'Run 01_create_classes.st first.']
    ifTrue: [
        (Smalltalk at: #AIHarnessPaneMorph) compile: 'initialize
    super initialize.
    self color: (Color r: 0.16 g: 0.17 b: 0.19).
    self borderWidth: 2.
    self borderColor: (Color r: 0.35 g: 0.36 b: 0.38).
    self extent: 340 @ 520.
    logMorph := TextMorph new contents: ''Scratch AI Harness - Phase 0''.
    logMorph position: 12 @ 12.
    logMorph extent: 316 @ 430.
    self addMorph: logMorph.
    self addMorph: (SimpleButtonMorph new
        label: ''Insert square'';
        target: AIHarness;
        actionSelector: #installDemo;
        position: 12 @ 452).
    self addMorph: (SimpleButtonMorph new
        label: ''Diagnose'';
        target: AIHarness;
        actionSelector: #diagnose;
        position: 120 @ 452).
    self addMorph: (SimpleButtonMorph new
        label: ''Close'';
        target: self;
        actionSelector: #delete;
        position: 210 @ 452)' classified: 'initialization'.

        (Smalltalk at: #AIHarnessPaneMorph) compile: 'log: aString
    logMorph ifNotNil: [logMorph contents: aString]' classified: 'accessing'.

        (Smalltalk at: #AIHarness) class compile: 'findFrame
    | frames |
    frames := ScratchFrameMorph allInstances select: [:m | m world notNil].
    frames isEmpty ifTrue: [^ nil].
    ^ frames first' classified: 'private'.

        (Smalltalk at: #AIHarness) class compile: 'open
    | pane frame |
    pane := Smalltalk at: #AIHarnessPane ifAbsent: [nil].
    (pane isNil or: [pane world isNil]) ifTrue: [
        pane := AIHarnessPaneMorph new.
        pane position: 60 @ 60.
        World addMorphFront: pane.
        Smalltalk at: #AIHarnessPane put: pane].
    pane comeToFront.
    frame := self findFrame.
    frame
        ifNil: [pane log: ''Scratch frame not found. Open Scratch, then click Diagnose.''] 
        ifNotNil: [pane log: ''Scratch frame found. Click Insert square.''].
    ^ pane' classified: 'actions'.

        (Smalltalk at: #AIHarness) class compile: 'diagnose
    | pane frames |
    pane := Smalltalk at: #AIHarnessPane ifAbsent: [nil].
    frames := ScratchFrameMorph allInstances select: [:m | m world notNil].
    pane ifNotNil: [
        pane log: ''ScratchFrameMorph instances: '', frames size printString,
            (frames isEmpty
                ifTrue: [''. No live frame found.'']
                ifFalse: [''. First frame has '', frames first workPane submorphs size printString, '' workPane morphs.'']) ].
    ^ frames' classified: 'actions'.

        (Smalltalk at: #AIHarness) class compile: 'installDemo
    | frame sprite tuple stack pane |
    pane := Smalltalk at: #AIHarnessPane ifAbsent: [nil].
    frame := self findFrame.
    frame ifNil: [
        pane ifNotNil: [pane log: ''Cannot insert: no live Scratch frame found.''].
        ^ self].
    sprite := frame scriptsPane target.
    (sprite isNil or: [sprite isKindOf: ScratchStageMorph]) ifTrue: [
        sprite := frame workPane submorphs
            detect: [:m | m isKindOf: ScratchSpriteMorph]
            ifNone: [nil]].
    sprite ifNil: [
        pane ifNotNil: [pane log: ''Cannot insert: no sprite selected.''].
        ^ self].
    tuple := #(
        #(EventHatMorph ''Scratch-StartClicked'')
        #(clearPenTrails)
        #(putPenDown)
        #(doRepeat 4 #(
            #(forward: 100)
            #(turnRight: 90)))
        #(putPenUp)).
    stack := sprite stackFromTupleList: tuple receiver: sprite.
    sprite addStack: stack.
    frame scriptsPane tabPane currentTab: ''Scripts''.
    sprite viewBlocksAndScripts.
    pane ifNotNil: [pane log: ''Inserted the square script. Click the green flag.''].
    ^ stack' classified: 'actions'.

        (Smalltalk at: #AIHarness) open].
