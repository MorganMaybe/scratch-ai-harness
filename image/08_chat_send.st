"Scratch AI Harness - chat Send path.
Adds AIChangeSetApplier and AIHarness>>sendPrompt, rebuilds the chat pane
with a Send button, and reopens it.

Run this after 07_chat_ui.st has been loaded once."

| oldPane |
(Smalltalk includesKey: #AIChangeSetApplier) ifFalse: [
    Object subclass: #AIChangeSetApplier
        instanceVariableNames: ''
        classVariableNames: 'Scripts UndoStack'
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIChangeSetApplier) class compile: 'scripts
    Scripts ifNil: [Scripts := Dictionary new].
    ^ Scripts' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'reset
    Scripts := Dictionary new' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'findFrame
    | frames |
    frames := ScratchFrameMorph allInstances select: [:m | m world notNil].
    frames isEmpty ifTrue: [^ nil].
    ^ frames first' classified: 'private'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'stage
    | frame |
    frame := self findFrame.
    ^ frame ifNil: [nil] ifNotNil: [frame workPane]' classified: 'private'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'targetNamed: name
    | frame stage sprite |
    frame := self findFrame.
    frame ifNil: [^ nil].
    stage := frame workPane.
    (name isNil or: [name = ''Stage'']) ifTrue: [^ stage].
    sprite := stage submorphs
        detect: [:m | (m isKindOf: ScratchSpriteMorph) and: [m objName = name]]
        ifNone: [nil].
    ^ sprite' classified: 'private'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'currentTargetName
    | frame target |
    frame := self findFrame.
    frame ifNil: [^ ''Sprite1''].
    target := frame scriptsPane target.
    (target isNil or: [target isKindOf: ScratchStageMorph]) ifTrue: [^ ''Stage''].
    ^ target objName' classified: 'private'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'addScript: id target: targetName tuples: tupleList
    | target stack |
    target := self targetNamed: targetName.
    target ifNil: [
        DialogBoxMorph inform: ''Unknown target: '', targetName asString.
        ^ nil].
    stack := target stackFromTupleList: tupleList receiver: target.
    target addStack: stack.
    self scripts at: id put: stack.
    ^ stack' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'replaceScript: id target: targetName tuples: tupleList
    | target stack old |
    old := self scripts at: id ifAbsent: [nil].
    old ifNil: [
        DialogBoxMorph inform: ''Cannot replace unknown script '', id asString.
        ^ nil].
    target := self targetNamed: targetName.
    target ifNil: [
        DialogBoxMorph inform: ''Unknown target: '', targetName asString.
        ^ nil].
    stack := target stackFromTupleList: tupleList receiver: target.
    old delete.
    target addStack: stack.
    self scripts at: id put: stack.
    ^ stack' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'deleteScript: id
    | old |
    old := self scripts at: id ifAbsent: [nil].
    old ifNil: [^ nil].
    old delete.
    self scripts removeKey: id ifAbsent: [].
    ^ nil' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'createVariable: name scope: scope initial: initial target: targetName
    | target scopeName |
    scopeName := scope asString.
    target := (scopeName = ''global'')
        ifTrue: [self stage]
        ifFalse: [self targetNamed: targetName].
    target ifNil: [^ nil].
    target addVariable: name.
    target setVar: name to: initial.
    ^ target' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'createVariable: name scope: scope initial: initial
    ^ self createVariable: name scope: scope initial: initial
        target: self currentTargetName' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'applyChange: change
    | action |
    action := change at: 1.
    action = #add ifTrue: [
        ^ self addScript: (change at: 2) target: (change at: 3) tuples: (change at: 4)].
    action = #replace ifTrue: [
        ^ self replaceScript: (change at: 2) target: (change at: 3) tuples: (change at: 4)].
    action = #delete ifTrue: [
        ^ self deleteScript: (change at: 2)].
    action = #createVariable ifTrue: [
        ^ (change size >= 5)
            ifTrue: [
                self createVariable: (change at: 2) scope: (change at: 3)
                    initial: (change at: 4) target: (change at: 5)]
            ifFalse: [
                self createVariable: (change at: 2) scope: (change at: 3)
                    initial: (change at: 4)]].
    ^ nil' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'apply: anArray
    | changes |
    changes := anArray.
    (changes isKindOf: Array) ifFalse: [^ 0].
    ((changes size >= 3) and: [(changes at: 1) = #apply])
        ifTrue: [changes := changes at: 3].
    changes do: [:change | self applyChange: change].
    self refresh.
    ^ changes size' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'refresh
    | frame target |
    frame := self findFrame.
    frame ifNil: [^ self].
    frame scriptsPane tabPane currentTab: ''Scripts''.
    target := frame scriptsPane target.
    target ifNotNil: [target viewBlocksAndScripts].
    ^ self' classified: 'applying'.

(Smalltalk at: #AIHarness) class compile: 'literalString: aString
    | out |
    out := WriteStream on: String new.
    out nextPut: $''.
    aString asString do: [:ch |
        ch = $'' ifTrue: [out nextPut: $''].
        out nextPut: ch].
    out nextPut: $''.
    ^ out contents' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'sendPrompt
    | pane prompt frame targetName client addr reply parsed kind id msg ack |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ self].
    pane acceptInput.
    prompt := pane inputText.
    prompt isEmpty ifTrue: [^ self].
    pane appendLog: ''You: '', prompt.
    pane clearInput.
    frame := self findFrame.
    targetName := ''Sprite1''.
    frame ifNotNil: [
        (frame scriptsPane target notNil and: [
            frame scriptsPane target isKindOf: ScratchSpriteMorph])
            ifTrue: [targetName := frame scriptsPane target objName]
            ifFalse: [targetName := ''Stage'']].
    id := Time millisecondClockValue.
    msg := ''#(#request '', id printString, '' #('', (self literalString: prompt), '') '', (self literalString: targetName), '')''.
    addr := NetNameResolver addressForName: ''127.0.0.1''.
    client := MessageSocket new.
    (client connectTo: addr port: 8765 waitSecs: 5)
        ifFalse: [
            pane appendLog: ''Bridge not reachable on 127.0.0.1:8765.''.
            ^ self].
    reply := client request: msg asByteArray timeoutSecs: 120.
    reply ifNil: [
        client destroy.
        pane appendLog: ''Bridge did not reply.''.
        ^ self].
    parsed := (Smalltalk at: #AILiteralReader) parse: reply asString.
    kind := parsed at: 1.
    kind = #result
        ifTrue: [
            (parsed at: 3) do: [:line | pane appendLog: line asString].
            (Smalltalk at: #AIChangeSetApplier)
                perform: #apply: with: (parsed at: 4).
            ack := client request: (''#(#applied '', id printString, '')'') asByteArray timeoutSecs: 10.
            ack ifNotNil: [pane appendLog: ''Applied. Click the green flag to try it.'']]
        ifFalse: [
            kind = #error
                ifTrue: [pane appendLog: ''Error: '', (parsed at: 3) asString]
                ifFalse: [pane appendLog: ''Bridge reply: '', reply asString]].
    client destroy.
    ^ nil' classified: 'chat'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'inputText: aString
    inputText := aString asString.
    ^ true' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'initialize
    super initialize.
    self color: (Color r: 0.16 g: 0.17 b: 0.19).
    self borderWidth: 2.
    self borderColor: (Color r: 0.35 g: 0.36 b: 0.38).
    self extent: 380 @ 560.
    inputText := ''Draw a square with the pen.''.
    logMorph := TextMorph new contents: ''Scratch AI Harness - Chat''.
    logMorph position: 12 @ 12.
    logMorph extent: 356 @ 390.
    self addMorph: logMorph.
    inputMorph := PluggableTextMorph on: self text: #inputText accept: #inputText:.
    inputMorph position: 12 @ 414.
    inputMorph extent: 356 @ 56.
    inputMorph color: Color white.
    inputMorph font: (ScratchFrameMorph getFont: #Label).
    self addMorph: inputMorph.
    self addMorph: (SimpleButtonMorph new
        label: ''Test input'';
        target: AIHarness;
        actionSelector: #testInput;
        position: 12 @ 486).
    self addMorph: (SimpleButtonMorph new
        label: ''Clear'';
        target: self;
        actionSelector: #clearChat;
        position: 112 @ 486).
    self addMorph: (SimpleButtonMorph new
        label: ''Close'';
        target: self;
        actionSelector: #delete;
        position: 192 @ 486).
    self addMorph: (SimpleButtonMorph new
        label: ''Send'';
        target: AIHarness;
        actionSelector: #sendPrompt;
        position: 272 @ 486)' classified: 'initialization'.

"Rebuild the pane so the new initialize (with Send) takes effect. Use
perform: for the just-defined selectors to avoid the workspace compile-time
unknown-selector menu."
oldPane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
oldPane ifNotNil: [oldPane delete].
Smalltalk at: #AIHarnessChat put: nil.
(Smalltalk at: #AIHarness) perform: #openChat.
