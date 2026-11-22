(Smalltalk includesKey: #AIHarnessChatPaneMorph) ifFalse: [
    BorderedMorph subclass: #AIHarnessChatPaneMorph
        instanceVariableNames: 'logMorph inputMorph inputText'
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

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
        position: 192 @ 486)' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'inputText
    ^ inputText ifNil: ['''']' classified: 'accessing'.

"PluggableTextMorph>>accept treats the setter's return value as a Boolean,
so this accessor must answer true rather than self."
(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'inputText: aString
    inputText := aString asString.
    ^ true' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'acceptInput
    inputMorph ifNotNil: [inputMorph accept]' classified: 'actions'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'clearInput
    inputText := ''''.
    inputMorph ifNotNil: [inputMorph setText: '''']' classified: 'actions'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'clearChat
    logMorph ifNotNil: [logMorph contents: ''Scratch AI Harness - Chat'']' classified: 'actions'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'appendLog: aString
    | old |
    logMorph ifNil: [^ self].
    old := logMorph contents asString.
    old isEmpty
        ifTrue: [logMorph contents: aString]
        ifFalse: [logMorph contents: old, String cr, aString]' classified: 'actions'.

(Smalltalk at: #AIHarness) class compile: 'openChat
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (pane isNil or: [pane world isNil]) ifTrue: [
        pane := AIHarnessChatPaneMorph new.
        pane position: 60 @ 60.
        World addMorphFront: pane.
        Smalltalk at: #AIHarnessChat put: pane].
    pane comeToFront.
    ^ pane' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'testInput
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ self].
    pane acceptInput.
    pane appendLog: ''You: '', pane inputText' classified: 'chat'.

"Use perform: because the workspace compiles the whole script before running it,
so a direct send of the just-defined openChat selector would trigger the
'Unknown selector' menu. Gotcha #1 in docs/SQUEAK_NOTES.md."
(Smalltalk at: #AIHarness) perform: #openChat.
