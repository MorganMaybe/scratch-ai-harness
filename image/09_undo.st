"Scratch AI Harness - undo of the last applied change set.
Adds an UndoStack class variable to AIChangeSetApplier, records inverse
operations for add/replace/delete/createVariable, adds an Undo button to the
chat pane, and reopens the pane.

Run this after 08_chat_send.st."

| oldPane classVars |
classVars := (Smalltalk at: #AIChangeSetApplier) classVarNames
    collect: [:s | s asString].
(classVars includes: 'UndoStack')
    ifFalse: [(Smalltalk at: #AIChangeSetApplier) addClassVarName: 'UndoStack'].

(Smalltalk at: #AIChangeSetApplier) class compile: 'undoStack
    UndoStack ifNil: [UndoStack := OrderedCollection new].
    ^ UndoStack' classified: 'undo'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'undoRecordFor: change
    | action id target old |
    action := change at: 1.
    action = #add ifTrue: [^ Array with: #add with: (change at: 2)].
    action = #replace ifTrue: [
        id := change at: 2.
        target := change at: 3.
        old := self scripts at: id ifAbsent: [nil].
        ^ Array with: #replace with: id with: target
            with: (old ifNil: [nil] ifNotNil: [old tupleSequence])].
    action = #delete ifTrue: [
        id := change at: 2.
        old := self scripts at: id ifAbsent: [nil].
        target := old ifNil: [self currentTargetName] ifNotNil: [old scriptOwner objName].
        ^ Array with: #delete with: id with: target
            with: (old ifNil: [nil] ifNotNil: [old tupleSequence])].
    action = #createVariable ifTrue: [
        ^ Array with: #createVariable with: (change at: 2)
            with: (change at: 3)
            with: ((change size >= 5)
                ifTrue: [change at: 5]
                ifFalse: [self currentTargetName])].
    ^ nil' classified: 'undo'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'undoRecord: record
    | action id target tuples |
    action := record at: 1.
    action = #add ifTrue: [^ self deleteScript: (record at: 2)].
    action = #replace ifTrue: [
        id := record at: 2.
        target := record at: 3.
        tuples := record at: 4.
        tuples ifNil: [^ nil].
        ^ self replaceScript: id target: target tuples: tuples].
    action = #delete ifTrue: [
        id := record at: 2.
        target := record at: 3.
        tuples := record at: 4.
        tuples ifNil: [^ nil].
        ^ self addScript: id target: target tuples: tuples].
    action = #createVariable ifTrue: [
        target := (record at: 3) = #global
            ifTrue: [self stage]
            ifFalse: [
                self targetNamed: ((record size >= 4)
                    ifTrue: [record at: 4]
                    ifFalse: [self currentTargetName])].
        target ifNotNil: [target deleteVariable: (record at: 2)].
        ^ target].
    ^ nil' classified: 'undo'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'undoLast
    | record |
    self undoStack isEmpty ifTrue: [^ false].
    record := self undoStack removeLast.
    record reverseDo: [:item | self undoRecord: item].
    self refresh.
    ^ true' classified: 'undo'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'apply: anArray
    | changes undo |
    changes := anArray.
    (changes isKindOf: Array) ifFalse: [^ 0].
    ((changes size >= 3) and: [(changes at: 1) = #apply])
        ifTrue: [changes := changes at: 3].
    undo := OrderedCollection new.
    changes do: [:change | undo add: (self undoRecordFor: change)].
    self undoStack addLast: undo.
    changes do: [:change | self applyChange: change].
    self refresh.
    ^ changes size' classified: 'applying'.

(Smalltalk at: #AIHarness) class compile: 'undoLast
    | applier pane |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNil: [^ self].
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (applier perform: #undoLast)
        ifTrue: [pane ifNotNil: [pane appendLog: ''Undid the last change set.'']]
        ifFalse: [pane ifNotNil: [pane appendLog: ''Nothing to undo.'']].
    ^ self' classified: 'chat'.

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
        position: 92 @ 486).
    self addMorph: (SimpleButtonMorph new
        label: ''Undo'';
        target: AIHarness;
        actionSelector: #undoLast;
        position: 152 @ 486).
    self addMorph: (SimpleButtonMorph new
        label: ''Send'';
        target: AIHarness;
        actionSelector: #sendPrompt;
        position: 222 @ 486).
    self addMorph: (SimpleButtonMorph new
        label: ''Close'';
        target: self;
        actionSelector: #delete;
        position: 302 @ 486)' classified: 'initialization'.

oldPane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
oldPane ifNotNil: [oldPane delete].
Smalltalk at: #AIHarnessChat put: nil.
(Smalltalk at: #AIHarness) perform: #openChat.
