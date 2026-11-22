"Scratch AI Harness - headless replies + real project context.
Adds:
  - AIHarnessChatPaneMorph>>logText and a #log control command
  - sendPromptText: returns the reply delta instead of 'ok send'
  - projectContext / literalFor: / hashForTuples: and a #context command
  - sendPrompt ships the context with every #request
  - non-modal problem reporting (no DialogBoxMorph.inform: from the apply path)
  - hash tracking so the bridge can spot scripts edited outside the harness

Run after 13_dev_server.st / 14_start_server.st. Do not reload the server file."

| classVars |
classVars := (Smalltalk at: #AIChangeSetApplier) classVarNames collect: [:s | s asString].
(classVars includes: 'AppliedHashes')
    ifFalse: [(Smalltalk at: #AIChangeSetApplier) addClassVarName: 'AppliedHashes'].

"--- non-modal problem reporting -------------------------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'reportProblem: aString
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNotNil: [pane appendLog: ''Problem: '', aString asString].
    ^ nil' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'recordHashFor: id tuples: tupleList
    AppliedHashes ifNil: [AppliedHashes := Dictionary new].
    AppliedHashes at: id asString put: ((Smalltalk at: #AIHarness) perform: #hashForTuples: with: tupleList).
    ^ self' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'userEditedId: id
    | recorded stack current |
    AppliedHashes ifNil: [^ false].
    recorded := AppliedHashes at: id ifAbsent: [nil].
    recorded ifNil: [^ false].
    stack := self scripts at: id ifAbsent: [nil].
    stack ifNil: [^ false].
    current := (Smalltalk at: #AIHarness) perform: #hashForTuples: with: stack tupleSequence.
    ^ recorded ~= current' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'addScript: id target: targetName tuples: tupleList
    | target stack |
    target := self targetNamed: targetName.
    target ifNil: [
        self reportProblem: ''Unknown target: '', targetName asString.
        ^ nil].
    stack := target stackFromTupleList: tupleList receiver: target.
    target addStack: stack.
    self scripts at: id put: stack.
    self recordHashFor: id tuples: tupleList.
    ^ stack' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'replaceScript: id target: targetName tuples: tupleList
    | target stack old |
    old := self scripts at: id ifAbsent: [nil].
    old ifNil: [
        self reportProblem: ''Cannot replace unknown script '', id asString.
        ^ nil].
    target := self targetNamed: targetName.
    target ifNil: [
        self reportProblem: ''Unknown target: '', targetName asString.
        ^ nil].
    stack := target stackFromTupleList: tupleList receiver: target.
    old delete.
    target addStack: stack.
    self scripts at: id put: stack.
    self recordHashFor: id tuples: tupleList.
    ^ stack' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'deleteScript: id
    | old |
    old := self scripts at: id ifAbsent: [nil].
    old ifNil: [^ nil].
    old delete.
    self scripts removeKey: id ifAbsent: [].
    AppliedHashes ifNotNil: [AppliedHashes removeKey: id ifAbsent: []].
    ^ nil' classified: 'applying'.

"--- chat pane log access ------------------------------------------------"
(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'logText
    logMorph ifNil: [^ ''''].
    ^ logMorph contents asString' classified: 'accessing'.

"--- literal serialization + stable hashing ------------------------------"
(Smalltalk at: #AIHarness) class compile: 'literalFor: anObject
    | out |
    (anObject isKindOf: Array) ifTrue: [
        out := WriteStream on: String new.
        out nextPutAll: ''#(''.
        anObject do: [:each | out nextPutAll: (self literalFor: each); nextPut: $ ].
        out nextPut: $).
        ^ out contents].
    (anObject isKindOf: String) ifTrue: [^ self literalString: anObject asString].
    (anObject isKindOf: Symbol) ifTrue: [^ ''#'', anObject asString].
    anObject ifNil: [^ ''nil''].
    ((anObject isKindOf: Boolean) or: [anObject isKindOf: Number])
        ifTrue: [^ anObject printString].
    ^ self literalString: anObject asString' classified: 'context'.

(Smalltalk at: #AIHarness) class compile: 'hashForTuples: tupleList
    | text h |
    text := self literalFor: tupleList.
    h := 0.
    text do: [:ch | h := (h * 31 + ch asInteger) \\ 1000000007].
    ^ h printString' classified: 'context'.

"--- project context -----------------------------------------------------"
"These two builders are bootstrap fallbacks only. 19_labels/25_project_registry
 replace scriptContextFor: with a label-aware version, 28_sprites_stage replaces
 spriteContextFor: with the 8-element sprite version, and 35_script_detail wraps
 the script builder to append lazy block detail. The includesSelector: guards
 keep a reload of this file from silently downgrading those installs (session 20
 regression: reloading 15 after 28/35 turned the context back into 7 elements).
 To repair an image that already lost them, reload 28 -> 34 -> 35."

((Smalltalk at: #AIHarness) class includesSelector: #scriptContextFor:) ifFalse: [
    (Smalltalk at: #AIHarness) class compile: 'scriptContextFor: aHat
    | tuples hash id registry owned edited hatName |
    tuples := aHat tupleSequence.
    hash := self hashForTuples: tuples.
    registry := (Smalltalk at: #AIChangeSetApplier) perform: #scripts.
    id := nil.
    registry keysDo: [:key | (registry at: key) == aHat ifTrue: [id := key asString]].
    owned := id notNil.
    owned ifFalse: [id := ''user-'', hash].
    edited := false.
    owned ifTrue: [edited := (Smalltalk at: #AIChangeSetApplier) perform: #userEditedId: with: id].
    hatName := (tuples first first) asString.
    ^ (OrderedCollection new
        add: id;
        add: hatName;
        add: hatName;
        add: tuples size;
        add: hash;
        add: owned;
        add: edited;
        yourself) asArray' classified: 'context'].

((Smalltalk at: #AIHarness) class includesSelector: #spriteContextFor:) ifFalse: [
    (Smalltalk at: #AIHarness) class compile: 'spriteContextFor: aSprite
    | isStage vars lists costumes sounds scripts |
    isStage := aSprite isKindOf: ScratchStageMorph.
    vars := [aSprite varNames asArray] ifError: [:e :r | #()].
    lists := #().
    isStage ifTrue: [lists := [(aSprite lists keys) asArray] ifError: [:e :r | #()]].
    costumes := [(aSprite costumeNames select: [:each | (each asString = ''-'') not]) asArray]
        ifError: [:e :r | #()].
    sounds := [(aSprite soundNames select: [:each | | soundName |
        soundName := each asString.
        (soundName = ''-'') not and: [(soundName findString: ''record'') = 0]]) asArray]
        ifError: [:e :r | #()].
    scripts := OrderedCollection new.
    [aSprite scripts do: [:aHat | scripts add: (self scriptContextFor: aHat)]]
        ifError: [:e :r | nil].
    ^ (OrderedCollection new
        add: aSprite objName asString;
        add: isStage;
        add: vars;
        add: lists;
        add: costumes;
        add: sounds;
        add: scripts asArray;
        yourself) asArray' classified: 'context'].

(Smalltalk at: #AIHarness) class compile: 'projectContext
    | frame stage targetName sprites |
    frame := self findFrame.
    frame ifNil: [^ nil].
    stage := frame workPane.
    stage ifNil: [^ nil].
    targetName := ''Stage''.
    (frame scriptsPane target notNil and: [frame scriptsPane target isKindOf: ScratchSpriteMorph])
        ifTrue: [targetName := frame scriptsPane target objName asString].
    sprites := OrderedCollection new.
    sprites add: (self spriteContextFor: stage).
    stage submorphs do: [:m |
        (m isKindOf: ScratchSpriteMorph) ifTrue: [sprites add: (self spriteContextFor: m)]].
    ^ (OrderedCollection new
        add: targetName;
        add: sprites asArray;
        yourself) asArray' classified: 'context'.

(Smalltalk at: #AIHarness) class compile: 'devContext
    | ctx |
    ctx := [self projectContext] ifError: [:e :r | nil].
    ctx ifNil: [^ ''error: no project context''].
    ^ self literalFor: ctx' classified: 'context'.

(Smalltalk at: #AIHarness) class compile: 'devLog
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ ''error: no chat pane''].
    ^ pane logText' classified: 'context'.

"--- chat send with context ----------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'sendPrompt
    | pane prompt frame targetName client addr reply parsed kind id msg ack context paneClass |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ ''error: no chat pane''].
    paneClass := Smalltalk at: #AIHarnessChatMorph ifAbsent: [nil].
    pane acceptInput.
    prompt := pane inputText.
    prompt isEmpty ifTrue: [^ ''error: empty prompt''].
    (paneClass notNil and: [pane isKindOf: paneClass])
        ifTrue: [
            pane appendUser: prompt.
            pane pending: true.
            pane status: ''Thinking...'']
        ifFalse: [pane appendLog: ''You: '', prompt].
    pane clearInput.
    frame := self findFrame.
    targetName := ''Sprite1''.
    frame ifNotNil: [
        (frame scriptsPane target notNil and: [
            frame scriptsPane target isKindOf: ScratchSpriteMorph])
            ifTrue: [targetName := frame scriptsPane target objName]
            ifFalse: [targetName := ''Stage'']].
    context := [self projectContext] ifError: [:e :r | nil].
    id := Time millisecondClockValue.
    msg := ''#(#request '', id printString, '' #('', (self literalString: prompt), '') '', (self literalString: targetName), '' ''.
    context ifNil: [msg := msg, ''nil''].
    context ifNotNil: [msg := msg, (self literalFor: context)].
    msg := msg, '')''.
    addr := NetNameResolver addressForName: ''127.0.0.1''.
    client := MessageSocket new.
    (client connectTo: addr port: 8765 waitSecs: 5)
        ifFalse: [
            pane appendError: ''Error: bridge not reachable on 127.0.0.1:8765''.
            (paneClass notNil and: [pane isKindOf: paneClass])
                ifTrue: [pane pending: false. pane status: ''Error''].
            ^ ''error: bridge not reachable''].
    reply := client request: msg asByteArray timeoutSecs: 300.
    reply ifNil: [
        client destroy.
        pane appendError: ''Error: bridge did not reply''.
        (paneClass notNil and: [pane isKindOf: paneClass])
            ifTrue: [pane pending: false. pane status: ''Error''].
        ^ ''error: no bridge reply''].
    parsed := (Smalltalk at: #AILiteralReader) parse: reply asString.
    kind := parsed at: 1.
    kind = #result
        ifTrue: [
            (parsed at: 3) do: [:line |
                (paneClass notNil and: [pane isKindOf: paneClass])
                    ifTrue: [pane appendAssistant: line asString]
                    ifFalse: [pane appendLog: line asString]].
            (Smalltalk at: #AIChangeSetApplier)
                perform: #apply: with: (parsed at: 4).
            ack := client request: (''#(#applied '', id printString, '')'') asByteArray timeoutSecs: 10.
            ack ifNotNil: [pane appendStatus: ''Applied. Click the green flag to try it.'']
                ifNil: [pane appendError: ''Error: applied, but the bridge did not acknowledge.'']]
        ifFalse: [
            kind = #error
                ifTrue: [pane appendError: ''Error: '', (parsed at: 3) asString]
                ifFalse: [pane appendAssistant: ''Bridge reply: '', reply asString]].
    client destroy.
    (paneClass notNil and: [pane isKindOf: paneClass])
        ifTrue: [
            pane pending: false.
            pane status: (kind = #error ifTrue: [''Error''] ifFalse: [''Ready'']).
            pane refreshCurrentPage].
    ^ nil' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'sendPromptText: aString
    | pane before after delta |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ ''error: no chat pane''].
    before := pane logText.
    pane setInputText: aString.
    self sendPrompt.
    after := pane logText.
    delta := after.
    (after size > before size and: [
        before isEmpty or: [(after copyFrom: 1 to: before size) = before]])
        ifTrue: [delta := after copyFrom: before size + 1 to: after size].
    ^ delta' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'undoLast
    | applier pane paneClass |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNil: [^ ''error: no applier''].
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    paneClass := Smalltalk at: #AIHarnessChatMorph ifAbsent: [nil].
    (applier perform: #undoLast)
        ifTrue: [
            pane ifNotNil: [
                (paneClass notNil and: [pane isKindOf: paneClass])
                    ifTrue: [pane appendStatus: ''Undid the last change set.''. pane status: ''Ready'']
                    ifFalse: [pane appendLog: ''Undid the last change set.'']].
            ^ ''ok undo''].
    pane ifNotNil: [
        (paneClass notNil and: [pane isKindOf: paneClass])
            ifTrue: [pane appendStatus: ''Nothing to undo.''. pane status: ''Ready'']
            ifFalse: [pane appendLog: ''Nothing to undo.'']].
    ^ ''nothing to undo''' classified: 'chat'.

"--- control commands ----------------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind |
    kind := req at: 1.
    kind = #load ifTrue: [
        ^ self load: (req at: 2)].
    kind = #send ifTrue: [
        ^ self sendPromptText: (req at: 2)].
    kind = #undo ifTrue: [
        ^ self undoLast].
    kind = #status ifTrue: [^ self devStatus].
    kind = #log ifTrue: [^ self devLog].
    kind = #context ifTrue: [^ self devContext].
    kind = #save ifTrue: [^ self saveAs: (req at: 2)].
    kind = #snapshot ifTrue: [
        Smalltalk snapshot: true andQuit: false.
        ^ ''ok snapshot''].
    ^ ''error: unknown command''' classified: 'dev server'.

"Sanity check the new selectors without relying on the pane."
(Smalltalk at: #AIHarness) perform: #hashForTuples: with: (Array with: #(#EventHatMorph 'Scratch-StartClicked')).
