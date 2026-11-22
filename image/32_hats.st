"Hat blocks and event wiring for the Scratch 2.0-era gaps.

Adds:
  - when stage clicked
  - when backdrop switches to [backdrop]
  - when loudness > [n]
  - when timer > [n]

The threshold hats reuse WhenHatBlockMorph's layout and process-start
machinery; only their condition and tuple shape differ."

"--- classes -----------------------------------------------------------"

(EventHatMorph subclass: #StageClickEventHatMorph
    instanceVariableNames: ''
    classVariableNames: ''
    poolDictionaries: ''
    category: 'Scratch-AI').

(EventHatMorph subclass: #BackdropHatMorph
    instanceVariableNames: 'choiceMorph'
    classVariableNames: ''
    poolDictionaries: ''
    category: 'Scratch-AI').

(WhenHatBlockMorph subclass: #WhenLoudnessHatMorph
    instanceVariableNames: ''
    classVariableNames: ''
    poolDictionaries: ''
    category: 'Scratch-AI').

(WhenHatBlockMorph subclass: #WhenTimerHatMorph
    instanceVariableNames: ''
    classVariableNames: ''
    poolDictionaries: ''
    category: 'Scratch-AI').

(Smalltalk at: #AIHarness) logLine: '32 classes ok'.

"--- when stage clicked -----------------------------------------------"

(Smalltalk at: #StageClickEventHatMorph) compile: 'initialize
    | label |
    super initialize.
    self removeAllMorphs.
    label := StringMorph contents: ''when stage clicked''
        font: (ScratchFrameMorph getFont: #Label).
    label color: Color white.
    self addMorphBack: label' classified: 'initialization'.

(Smalltalk at: #StageClickEventHatMorph) compile: 'eventName
    ^ ''Scratch-StageClicked''' classified: 'other'.

(Smalltalk at: #StageClickEventHatMorph) compile: 'asBlockTuple
    ^ Array with: self class name' classified: 'other'.

(Smalltalk at: #StageClickEventHatMorph) compile: 'printHatNameOn: aStream
    aStream nextPutAll: ''when stage clicked''; cr' classified: 'other'.

(Smalltalk at: #StageClickEventHatMorph) compile: 'helpScreenName
    ^ ''startHat''' classified: 'other'.

"--- when backdrop switches to [name] ---------------------------------"

(Smalltalk at: #BackdropHatMorph) compile: 'initialize
    | label |
    super initialize.
    self removeAllMorphs.
    label := StringMorph contents: ''when backdrop switches to''
        font: (ScratchFrameMorph getFont: #Label).
    label color: Color white.
    self addMorphBack: label.
    choiceMorph := ChoiceArgMorph new
        getOptionsSelector: #costumeNames;
        choice: ''background1''.
    self addMorphBack: choiceMorph' classified: 'initialization'.

(Smalltalk at: #BackdropHatMorph) compile: 'choice
    ^ choiceMorph ifNil: [''''] ifNotNil: [choiceMorph choice]' classified: 'accessing'.

(Smalltalk at: #BackdropHatMorph) compile: 'choice: aString
    choiceMorph ifNotNil: [choiceMorph choice: aString asString].
    self fixBlockLayout' classified: 'accessing'.

(Smalltalk at: #BackdropHatMorph) compile: 'eventName
    ^ ''Scratch-Backdrop:'', self choice asString' classified: 'other'.

(Smalltalk at: #BackdropHatMorph) compile: 'asBlockTuple
    ^ Array with: self class name with: self choice' classified: 'other'.

(Smalltalk at: #BackdropHatMorph) compile: 'printHatNameOn: aStream
    aStream nextPutAll: ''when backdrop switches to '', self choice asString; cr' classified: 'other'.

(Smalltalk at: #BackdropHatMorph) compile: 'helpScreenName
    ^ ''startHat''' classified: 'other'.

"--- threshold hats ---------------------------------------------------"

(Smalltalk at: #WhenLoudnessHatMorph) compile: 'initialize
    | label |
    super initialize.
    self removeAllMorphs.
    argMorph := ExpressionArgMorph new numExpression: ''10''.
    label := StringMorph contents: ''when loudness >''
        font: (ScratchFrameMorph getFont: #Label).
    label color: Color white.
    self addMorphBack: label.
    self addMorphBack: argMorph' classified: 'initialization'.

(Smalltalk at: #WhenLoudnessHatMorph) compile: 'threshold
    ^ argMorph evaluate asNumberNoError' classified: 'accessing'.

(Smalltalk at: #WhenLoudnessHatMorph) compile: 'threshold: aNumber
    argMorph ifNotNil: [argMorph defaultValue: aNumber].
    self fixBlockLayout' classified: 'accessing'.

(Smalltalk at: #WhenLoudnessHatMorph) compile: 'evaluateCondition
    ^ self scriptOwner soundLevel > self threshold' classified: 'other'.

(Smalltalk at: #WhenLoudnessHatMorph) compile: 'asBlockTuple
    ^ Array with: self class name with: self threshold' classified: 'other'.

(Smalltalk at: #WhenLoudnessHatMorph) compile: 'printHatNameOn: aStream
    aStream nextPutAll: ''when loudness > '', self threshold printString; cr' classified: 'other'.

(Smalltalk at: #WhenTimerHatMorph) compile: 'initialize
    | label |
    super initialize.
    self removeAllMorphs.
    argMorph := ExpressionArgMorph new numExpression: ''1''.
    label := StringMorph contents: ''when timer >''
        font: (ScratchFrameMorph getFont: #Label).
    label color: Color white.
    self addMorphBack: label.
    self addMorphBack: argMorph' classified: 'initialization'.

(Smalltalk at: #WhenTimerHatMorph) compile: 'threshold
    ^ argMorph evaluate asNumberNoError' classified: 'accessing'.

(Smalltalk at: #WhenTimerHatMorph) compile: 'threshold: aNumber
    argMorph ifNotNil: [argMorph defaultValue: aNumber].
    self fixBlockLayout' classified: 'accessing'.

(Smalltalk at: #WhenTimerHatMorph) compile: 'evaluateCondition
    ^ self scriptOwner timer > self threshold' classified: 'other'.

(Smalltalk at: #WhenTimerHatMorph) compile: 'asBlockTuple
    ^ Array with: self class name with: self threshold' classified: 'other'.

(Smalltalk at: #WhenTimerHatMorph) compile: 'printHatNameOn: aStream
    aStream nextPutAll: ''when timer > '', self threshold printString; cr' classified: 'other'.

"--- block spec -> hat instance ---------------------------------------"

((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseBlockFromSpec:color:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseBlockFromSpec:color:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #blockFromSpec:color:)].
(Smalltalk at: #ScriptableScratchMorph) compile: 'blockFromSpec: spec color: blockColor
    | blockType |
    blockType := spec at: 2.
    (#(A B U T) includes: blockType) ifTrue: [
        ^ (self aiHatBlockForSpec: spec) color: blockColor].
    ^ self baseBlockFromSpec: spec color: blockColor' classified: 'blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'aiHatBlockForSpec: spec
    | selector hat |
    selector := (spec at: 3) asSymbol.
    selector = #whenStageClicked ifTrue: [
        ^ StageClickEventHatMorph new scriptOwner: self].
    selector = #whenBackdropSwitches: ifTrue: [
        hat := BackdropHatMorph new scriptOwner: self.
        self costumeNames size > 0 ifTrue: [hat choice: self costumeNames first].
        ^ hat].
    selector = #whenLoudnessGreater: ifTrue: [
        ^ WhenLoudnessHatMorph new scriptOwner: self].
    selector = #whenTimerGreater: ifTrue: [
        ^ WhenTimerHatMorph new scriptOwner: self].
    ^ nil' classified: 'blocks'.

(Smalltalk at: #AIHarness) logLine: '32 hats/spec ok'.

"--- tuple conversion -------------------------------------------------"

((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseBlockFromTuple:receiver:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseBlockFromTuple:receiver:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #blockFromTuple:receiver:)].
(Smalltalk at: #AIHarness) logLine: '32 base tuple copied'.
(Smalltalk at: #ScriptableScratchMorph) compile: 'blockFromTuple: tuple receiver: scriptOwner
    | k |
    k := tuple first.
    (#(StageClickEventHatMorph BackdropHatMorph WhenLoudnessHatMorph WhenTimerHatMorph) includes: k)
        ifTrue: [^ self hatBlockFromTuple: tuple receiver: scriptOwner].
    ^ self baseBlockFromTuple: tuple receiver: scriptOwner' classified: 'blocks'.
(Smalltalk at: #AIHarness) logLine: '32 tuple wrapper ok'.

((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseHatBlockFromTuple:receiver:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseHatBlockFromTuple:receiver:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #hatBlockFromTuple:receiver:)].
(Smalltalk at: #AIHarness) logLine: '32 base hat copied'.
(Smalltalk at: #ScriptableScratchMorph) compile: 'hatBlockFromTuple: tuple receiver: scriptOwner
    | blockClass block |
    blockClass := Smalltalk at: tuple first.
    blockClass = StageClickEventHatMorph ifTrue: [
        ^ blockClass new scriptOwner: scriptOwner].
    blockClass = BackdropHatMorph ifTrue: [
        block := blockClass new scriptOwner: scriptOwner.
        tuple size > 1 ifTrue: [block choice: (tuple at: 2)].
        ^ block].
    blockClass = WhenLoudnessHatMorph ifTrue: [
        block := blockClass new scriptOwner: scriptOwner.
        tuple size > 1 ifTrue: [block threshold: (tuple at: 2)].
        ^ block].
    blockClass = WhenTimerHatMorph ifTrue: [
        block := blockClass new scriptOwner: scriptOwner.
        tuple size > 1 ifTrue: [block threshold: (tuple at: 2)].
        ^ block].
    ^ self baseHatBlockFromTuple: tuple receiver: scriptOwner' classified: 'scratch'.

(Smalltalk at: #AIHarness) logLine: '32 tuples ok'.

"--- event dispatch ---------------------------------------------------"

((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseEventReceived:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseEventReceived:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #eventReceived:)].
(Smalltalk at: #ScriptableScratchMorph) compile: 'eventReceived: event
    | targetScripts |
    targetScripts := #().
    event name = ''Scratch-StageClicked'' ifTrue: [
        targetScripts := self scripts select: [:s | s class == StageClickEventHatMorph]]
    ifFalse: [
        (event name beginsWith: ''Scratch-Backdrop:'') ifTrue: [
            targetScripts := self scripts select: [:s |
                (s class == BackdropHatMorph) and: [
                    s eventName caseInsensitiveEqual: event name]]]
        ifFalse: [^ self baseEventReceived: event]].
    ^ (targetScripts asArray collect: [:script | script startForEvent: event])
        select: [:p | p notNil]' classified: 'other ops'.

(Smalltalk at: #AIHarness) logLine: '32 events ok'.

"Stage backdrop changes broadcast an event named for the new backdrop."
(Smalltalk at: #ScratchStageMorph) compile: 'lookLike: costumeNameOrIndex
    | old new |
    old := [self costume mediaName] ifError: [''''].
    super lookLike: costumeNameOrIndex.
    new := [self costume mediaName] ifError: [''''].
    (old asString ~= new asString) ifTrue: [
        self broadcastEventNamed: ''Scratch-Backdrop:'', new asString with: 0]' classified: 'looks ops'.

"Stage clicks broadcast after the normal click handling."
(Smalltalk at: #ScratchStageMorph) compile: 'mouseDown: evt
    evt hand newKeyboardFocus: nil.
    evt hand toolType ifNotNil: [evt hand toolType: nil].
    evt rightButtonPressed
        ifTrue: [Sensor waitNoButton. ^ self rightButtonMenu]
        ifFalse: [
            self click: evt.
            self broadcastEventNamed: ''Scratch-StageClicked'' with: 0]' classified: 'event handling'.

"Enable condition hats (the stock implementation is disabled)."
((Smalltalk at: #ScratchFrameMorph) includesSelector: #baseProcessWhenConditions) ifFalse: [
    (Smalltalk at: #ScratchFrameMorph) methodDict
        at: #baseProcessWhenConditions
        put: ((Smalltalk at: #ScratchFrameMorph) methodDict at: #processWhenConditions)].
(Smalltalk at: #ScratchFrameMorph) compile: 'processWhenConditions
    | objList |
    objList := workPane submorphs select: [:m | m isKindOf: ScriptableScratchMorph].
    objList := objList copyWith: workPane.
    objList do: [:obj |
        obj scripts do: [:hat |
            (hat isKindOf: WhenHatBlockMorph) ifTrue: [
                (hat hasRunningProcess not and: [hat triggered]) ifTrue: [
                    hat start; layoutChanged]]]]' classified: 'stepping'.

(Smalltalk at: #AIHarness) logLine: '32 process ok'.

"Rebuild tuple lookup and refresh the palette."
(Smalltalk at: #ScriptableScratchMorph) buildBlockSpecDictionary.
(Smalltalk at: #AIHarness) logLine: 'hats loaded'.
