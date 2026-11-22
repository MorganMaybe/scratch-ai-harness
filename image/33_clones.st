"Scratch 2.0-style temporary clones for the AI harness.

Scratch 1.4 already contains dormant clone machinery (cloneAndSend:, isClone,
allClones, deleteAllClones). This file finishes the wiring:

  - create clone of [myself/other sprite]
  - delete this clone
  - when I start as a clone
  - 300-clone limit
  - clones persist until deleted or stop all
  - touching [sprite]? also sees that sprite's clones

Clones are runtime-only: they live in the stage submorphs, never in the sprite
corral (`sprites`), so they are not saved and do not appear in the AI context."

"--- clone hat ----------------------------------------------------------"

(EventHatMorph subclass: #CloneEventHatMorph
    instanceVariableNames: ''
    classVariableNames: ''
    poolDictionaries: ''
    category: 'Scratch-AI').

(Smalltalk at: #CloneEventHatMorph) compile: 'initialize
    | label |
    super initialize.
    self removeAllMorphs.
    label := StringMorph contents: ''when I start as a clone''
        font: (ScratchFrameMorph getFont: #Label).
    label color: Color white.
    self addMorphBack: label' classified: 'initialization'.

(Smalltalk at: #CloneEventHatMorph) compile: 'eventName
    ^ ''Scratch-CloneEvent''' classified: 'other'.

(Smalltalk at: #CloneEventHatMorph) compile: 'eventName: ignored
    ^ self' classified: 'other'.

(Smalltalk at: #CloneEventHatMorph) compile: 'asBlockTuple
    ^ Array with: self class name' classified: 'other'.

(Smalltalk at: #CloneEventHatMorph) compile: 'printHatNameOn: aStream
    aStream nextPutAll: ''when I start as a clone''; cr' classified: 'other'.

(Smalltalk at: #CloneEventHatMorph) compile: 'helpScreenName
    ^ ''whenHat''' classified: 'other'.

(Smalltalk at: #AIHarness) logLine: '33 clone hat ok'.

"--- block specs and tuple/palette wiring -------------------------------"

Smalltalk at: #AICloneBlockExtras put: #(
    'control'
        ('when I start as a clone'    L    whenCloneStart)
        ('create clone of %M'         -    createCloneOf:)
        ('delete this clone'          -    deleteThisClone)
).
(Smalltalk at: #AIHarness) logLine: '33 extras ok'.

((Smalltalk at: #ScratchSpriteMorph) class includesSelector: #baseCloneBlockSpecs) ifFalse: [
    (Smalltalk at: #ScratchSpriteMorph) class methodDict
        at: #baseCloneBlockSpecs
        put: ((Smalltalk at: #ScratchSpriteMorph) class methodDict at: #blockSpecs)].
(Smalltalk at: #AIHarness) logLine: '33 base specs ok'.
(Smalltalk at: #ScratchSpriteMorph) class compile: 'blockSpecs
    ^ self baseCloneBlockSpecs, (Smalltalk at: #AICloneBlockExtras)' classified: 'scratch'.
(Smalltalk at: #AIHarness) logLine: '33 blockSpecs ok'.

"Clone hat type L, before the 32_hats wrapper (this is an instance method)."
((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseCloneBlockFromSpec:color:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseCloneBlockFromSpec:color:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #blockFromSpec:color:)].
(Smalltalk at: #AIHarness) logLine: '33 base fromSpec ok'.
(Smalltalk at: #ScriptableScratchMorph) compile: 'blockFromSpec: spec color: blockColor
    | blockType |
    blockType := spec at: 2.
    blockType = #L ifTrue: [
        ^ CloneEventHatMorph new scriptOwner: self; color: blockColor].
    ^ self baseCloneBlockFromSpec: spec color: blockColor' classified: 'blocks'.
(Smalltalk at: #AIHarness) logLine: '33 fromSpec ok'.

"Clone hat tuples, before the 32_hats wrapper."
((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseCloneBlockFromTuple:receiver:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseCloneBlockFromTuple:receiver:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #blockFromTuple:receiver:)].
(Smalltalk at: #ScriptableScratchMorph) compile: 'blockFromTuple: tuple receiver: scriptOwner
    tuple first = #CloneEventHatMorph ifTrue: [
        ^ CloneEventHatMorph new scriptOwner: scriptOwner].
    ^ self baseCloneBlockFromTuple: tuple receiver: scriptOwner' classified: 'blocks'.
(Smalltalk at: #AIHarness) logLine: '33 fromTuple ok'.

"Clone event dispatch, before the 32_hats wrapper."
((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseCloneEventReceived:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseCloneEventReceived:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #eventReceived:)].
(Smalltalk at: #ScriptableScratchMorph) compile: 'eventReceived: event
    | targetScripts |
    event name = ''Scratch-CloneEvent'' ifTrue: [
        targetScripts := self scripts select: [:s | s class == CloneEventHatMorph].
        ^ (targetScripts asArray collect: [:script | script startForEvent: event])
            select: [:p | p notNil]].
    ^ self baseCloneEventReceived: event' classified: 'other ops'.

"New %M argument: myself or another sprite (not mouse/edge)."
((Smalltalk at: #CommandBlockMorph) includesSelector: #baseCloneArgMorphFor:) ifFalse: [
    (Smalltalk at: #CommandBlockMorph) methodDict
        at: #baseCloneArgMorphFor:
        put: ((Smalltalk at: #CommandBlockMorph) methodDict at: #uncoloredArgMorphFor:)].
(Smalltalk at: #CommandBlockMorph) compile: 'uncoloredArgMorphFor: specString
    | code |
    code := specString at: 2.
    code = $M ifTrue: [
        ^ ChoiceArgMorph new getOptionsSelector: #cloneTargetNames; choice: ''myself''].
    ^ self baseCloneArgMorphFor: specString' classified: 'private'.

(Smalltalk at: #AIHarness) logLine: '33 clone specs ok'.

"--- clone operations ---------------------------------------------------"

(Smalltalk at: #ScriptableScratchMorph) compile: 'cloneTargetNames
    | stage names |
    stage := self ownerThatIsA: ScratchStageMorph.
    names := OrderedCollection new.
    names add: ''myself''.
    stage ifNotNil: [
        stage sprites do: [:s |
            ((s ~~ self) and: [s objName notNil]) ifTrue: [
                names add: s objName asString]]].
    ^ names asArray' classified: 'clone ops'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'cloneTargetFor: aTarget
    | stage text |
    aTarget ifNil: [^ nil].
    (aTarget isKindOf: ScratchSpriteMorph) ifTrue: [^ aTarget].
    text := aTarget asString.
    text = ''myself'' ifTrue: [^ self].
    stage := self ownerThatIsA: ScratchStageMorph.
    stage ifNil: [^ nil].
    ^ stage sprites detect: [:s | (s objName asString) caseInsensitiveEqual: text] ifNone: [nil]' classified: 'clone ops'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'aiCloneRoot
    | root parent |
    root := self.
    [(parent := root valueOfProperty: #cloneParent) notNil] whileTrue: [
        root := parent].
    ^ root' classified: 'clone ops'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'cloneAndSend: msgName
    "Clone this sprite and send the clone (and only the clone) the given message."
    | frame clone |
    frame := self ownerThatIsA: ScratchFrameMorph.
    frame ifNil: [^ self].
    clone := self fullCopy.
    clone objName: objName asString, '' clone''.
    clone isClone: true.
    clone setProperty: #cloneParent toValue: self aiCloneRoot.
    clone blocksBin allMorphsDo: [:m |
        (m isKindOf: BlockMorph) ifTrue: [m stop]].
    frame workPane addMorph: clone.
    clone eventReceived: (ScratchEvent new name: msgName asString argument: 0).
    ^ clone' classified: 'clone ops'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'createCloneOf: aTarget
    | stage target limit |
    stage := self ownerThatIsA: ScratchStageMorph.
    stage ifNil: [^ self].
    limit := Smalltalk at: #AICloneLimit ifAbsent: [300].
    stage allClones size >= limit ifTrue: [^ self].
    target := self cloneTargetFor: aTarget.
    target ifNil: [^ self].
    (target isKindOf: ScratchSpriteMorph) ifFalse: [^ self].
    target cloneAndSend: ''Scratch-CloneEvent''.
    ^ self' classified: 'clone ops'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'deleteThisClone
    isClone ifFalse: [^ self].
    self scripts do: [:s | [s stop] ifError: [:e :r | nil]].
    self delete.
    ^ self' classified: 'clone ops'.

"2.0 persistence: a clone stays until delete this clone or stop all. The stock
1.4 helper would delete a clone as soon as no script is running."
(Smalltalk at: #ScratchStageMorph) compile: 'deleteTerminatedClones
    "Scratch 2.0 clones persist until explicitly deleted or stop all."
    ^ self' classified: 'clones'.

(Smalltalk at: #AIHarness) logLine: '33 clone ops ok'.

"Fix name resolution for plain-String targets. In this image original sprite
names are UTF8 while AI literals are String, and UTF8 = String is false in that
direction, so stock coerceSpriteArg: misses the sprite."
((Smalltalk at: #ScriptableScratchMorph) includesSelector: #baseCloneCoerceSpriteArg:) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) methodDict
        at: #baseCloneCoerceSpriteArg:
        put: ((Smalltalk at: #ScriptableScratchMorph) methodDict at: #coerceSpriteArg:)].
(Smalltalk at: #ScriptableScratchMorph) compile: 'coerceSpriteArg: anObject
    | s targetName |
    (anObject isKindOf: ScriptableScratchMorph) ifTrue: [^ anObject].
    (anObject isKindOf: Symbol) ifTrue: [^ anObject].
    targetName := anObject isNumber ifTrue: [anObject printString] ifFalse: [anObject].
    (s := self ownerThatIsA: ScratchStageMorph) ifNil: [^ nil].
    s submorphsDo: [:m |
        ((m isKindOf: ScriptableScratchMorph) and: [
            (m objName asString) caseInsensitiveEqual: (targetName asString)])
            ifTrue: [^ m]].
    ^ nil' classified: 'sensing ops'.

(Smalltalk at: #AIHarness) logLine: '33 coerce fixed'.

"--- clone-aware touching -----------------------------------------------"

((Smalltalk at: #ScratchSpriteMorph) includesSelector: #baseCloneTouching:) ifFalse: [
    (Smalltalk at: #ScratchSpriteMorph) methodDict
        at: #baseCloneTouching:
        put: ((Smalltalk at: #ScratchSpriteMorph) methodDict at: #touching:)].
(Smalltalk at: #ScratchSpriteMorph) compile: 'touching: anObject
    "2.0: touching [sprite]? is true for the original or any of its clones."
    | target stage |
    target := self coerceSpriteArg: anObject.
    (target isKindOf: ScratchSpriteMorph) ifTrue: [
        (self baseCloneTouching: target) ifTrue: [^ true].
        stage := self ownerThatIsA: ScratchStageMorph.
        stage ifNotNil: [
            stage allClones do: [:clone |
                (((clone valueOfProperty: #cloneParent) == target) and: [
                    self baseCloneTouching: clone]) ifTrue: [^ true]]].
        ^ false].
    ^ self baseCloneTouching: target' classified: 'sensing ops'.

(Smalltalk at: #AIHarness) logLine: '33 clone touching ok'.

Smalltalk at: #AICloneLimit put: (Smalltalk at: #AICloneLimit ifAbsent: [300]).
(Smalltalk at: #ScriptableScratchMorph) buildBlockSpecDictionary.
(Smalltalk at: #AIHarness) logLine: 'clones loaded'.
