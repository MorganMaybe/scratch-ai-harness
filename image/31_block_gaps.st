"Small block-gap pack for the AI harness.

Adds Scratch 2.0-era blocks that are cheap in 1.4:
  - current [year/month/date/day of week/hour/minute/second]
  - days since 2000, username (offline placeholder)
  - costume name / backdrop name reporters and attributes
  - set rotation style
  - set/change [attribute] of [sprite]
  - item # of [thing] in [list], show/hide list
  - stop other scripts in sprite
  - go to back / go forward layers
  - key [any] pressed

The block palettes are extended without rewriting the stock blockSpecs
methods: each class's original blockSpecs is preserved as baseBlockSpecs
and a new blockSpecs appends the AI extras.

Hats (when backdrop switches, when loudness/timer >, when stage clicked)
live in 32_hats.st."

"--- extra block specs -------------------------------------------------"

Smalltalk at: #AICommonBlockExtras put: #(
    'control'
        ('when loudness > %n'        U    whenLoudnessGreater:)
        ('when timer > %n'            T    whenTimerGreater:)
        ('stop other scripts in sprite' - stopOtherScripts)
    'sensing'
        ('current %z'                r    current:)
        ('days since 2000'            r    daysSince2000)
        ('username'                    r    username)
        ('set %a of %m to %s'        -    setAttribute:of:to:)
        ('change %a of %m by %n'    -    changeAttribute:of:by:)
    'list'
        ('show list %L'                -    showList:)
        ('hide list %L'                -    hideList:)
        ('item # of %s in %L'        r    itemNumOf:inList:)
).

Smalltalk at: #AISpriteBlockExtras put: #(
    'motion'
        ('set rotation style %R'    -    setRotationStyle:)
    'looks'
        ('costume name'                r    costumeName)
        ('go to back'                -    goToBack)
        ('go forward %n layers'        -    goForwardByLayers:)
).

Smalltalk at: #AIStageBlockExtras put: #(
    'control'
        ('when stage clicked'        A    whenStageClicked)
        ('when backdrop switches to %l' B whenBackdropSwitches:)
    'looks'
        ('backdrop name'            r    backgroundName)
).

"Preserve each stock blockSpecs method, then append the extras."
((Smalltalk at: #ScriptableScratchMorph) class includesSelector: #baseBlockSpecs) ifFalse: [
    (Smalltalk at: #ScriptableScratchMorph) class methodDict
        at: #baseBlockSpecs
        put: ((Smalltalk at: #ScriptableScratchMorph) class methodDict at: #blockSpecs)].
(Smalltalk at: #ScriptableScratchMorph) class compile: 'blockSpecs
    ^ ScriptableScratchMorph baseBlockSpecs, (Smalltalk at: #AICommonBlockExtras)' classified: 'scratch'.

((Smalltalk at: #ScratchSpriteMorph) class includesSelector: #baseBlockSpecs) ifFalse: [
    (Smalltalk at: #ScratchSpriteMorph) class methodDict
        at: #baseBlockSpecs
        put: ((Smalltalk at: #ScratchSpriteMorph) class methodDict at: #blockSpecs)].
(Smalltalk at: #ScratchSpriteMorph) class compile: 'blockSpecs
    ^ self baseBlockSpecs, (Smalltalk at: #AISpriteBlockExtras)' classified: 'scratch'.

((Smalltalk at: #ScratchStageMorph) class includesSelector: #baseBlockSpecs) ifFalse: [
    (Smalltalk at: #ScratchStageMorph) class methodDict
        at: #baseBlockSpecs
        put: ((Smalltalk at: #ScratchStageMorph) class methodDict at: #blockSpecs)].
(Smalltalk at: #ScratchStageMorph) class compile: 'blockSpecs
    ^ self baseBlockSpecs, (Smalltalk at: #AIStageBlockExtras)' classified: 'scratch'.

"New argument menus: %R rotation style, %z current time part."
((Smalltalk at: #CommandBlockMorph) includesSelector: #baseUncoloredArgMorphFor:) ifFalse: [
    (Smalltalk at: #CommandBlockMorph) methodDict
        at: #baseUncoloredArgMorphFor:
        put: ((Smalltalk at: #CommandBlockMorph) methodDict at: #uncoloredArgMorphFor:)].
(Smalltalk at: #CommandBlockMorph) compile: 'uncoloredArgMorphFor: specString
    | code |
    code := specString at: 2.
    code = $R ifTrue: [
        ^ ChoiceArgMorph new getOptionsSelector: #rotationStyleNames; choice: ''all around''].
    code = $z ifTrue: [
        ^ ChoiceArgMorph new getOptionsSelector: #currentOptions; choice: ''year''].
    ^ self baseUncoloredArgMorphFor: specString' classified: 'private'.

"--- names, time, lists, rotation -------------------------------------"

(Smalltalk at: #ScriptableScratchMorph) compile: 'costumeName
    ^ self costume mediaName' classified: 'ai blocks'.

(Smalltalk at: #ScratchStageMorph) compile: 'backgroundName
    ^ self costume mediaName' classified: 'ai blocks'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'attributeNames
    ^ #(''x position'' ''y position'' ''direction'' ''costume #'' ''costume name'' ''size'' ''volume'')' classified: 'sensing ops'.

(Smalltalk at: #ScratchStageMorph) compile: 'attributeNames
    ^ #(''background #'' ''backdrop name'' ''volume'')' classified: 'sensing ops'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'getAttribute: attr
    | a |
    (vars includesKey: attr) ifTrue: [^ vars at: attr].
    a := attr localized.
    ''x position'' localized = a ifTrue: [^ self xpos].
    ''y position'' localized = a ifTrue: [^ self ypos].
    ''direction'' localized = a ifTrue: [^ self heading].
    ''costume #'' localized = a ifTrue: [^ self costumeIndex].
    ''costume name'' localized = a ifTrue: [^ self costumeName].
    ''size'' localized = a ifTrue: [^ self scale].
    ''volume'' localized = a ifTrue: [^ self volume].
    ^ 0' classified: 'sensing ops'.

(Smalltalk at: #ScratchStageMorph) compile: 'getAttribute: attr
    | a |
    (vars includesKey: attr) ifTrue: [^ vars at: attr].
    a := attr localized.
    ''background #'' localized = a ifTrue: [^ self backgroundIndex].
    ''backdrop name'' localized = a ifTrue: [^ self backgroundName].
    ''volume'' localized = a ifTrue: [^ self volume].
    ^ 0' classified: 'sensing ops'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'rotationStyleNames
    ^ #(''all around'' ''left-right'' ''don''''t rotate'')' classified: 'ai blocks'.

(Smalltalk at: #ScratchSpriteMorph) compile: 'setRotationStyle: aString
    | s |
    s := aString asString.
    s = ''left-right'' ifTrue: [^ self rotationStyle: #leftRight].
    (s = ''don''''t rotate'') ifTrue: [^ self rotationStyle: #none].
    ^ self rotationStyle: #normal' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'currentOptions
    ^ #(''year'' ''month'' ''date'' ''day of week'' ''hour'' ''minute'' ''second'')' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'current: aString
    | parts date time |
    parts := Time dateAndTimeNow.
    date := parts at: 1.
    time := parts at: 2.
    aString asString = ''year'' ifTrue: [^ date year].
    aString asString = ''month'' ifTrue: [^ date monthIndex].
    aString asString = ''date'' ifTrue: [^ date dayOfMonth].
    aString asString = ''day of week'' ifTrue: [
        "Scratch 2.0: Sunday=1 ... Saturday=7; Squeak: Monday=1 ... Sunday=7"
        ^ ((date weekdayIndex + 6) \\ 7) + 1].
    aString asString = ''hour'' ifTrue: [^ time hours].
    aString asString = ''minute'' ifTrue: [^ time minutes].
    aString asString = ''second'' ifTrue: [^ time seconds].
    ^ 0' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'daysSince2000
    ^ Date today subtractDate: (Date newDay: 1 month: #January year: 2000)' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'username
    "Offline placeholder: Scratch 2.0 account names do not exist here."
    ^ ''player''' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'itemNumOf: anObject inList: listName
    | list |
    list := self listNamed: listName ifNone: [^ 0].
    1 to: list lineCount do: [:i |
        ((list lineAt: i) asString = anObject asString) ifTrue: [^ i]].
    ^ 0' classified: 'list ops'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'showList: listName
    | list stage existing |
    list := self listNamed: listName ifNone: [^ self].
    stage := self ownerThatIsA: ScratchStageMorph.
    stage ifNil: [^ self].
    existing := stage submorphs detect: [:m |
        (m isKindOf: ScratchListMorph) and: [
            m listName = listName and: [m target = self]]] ifNone: [nil].
    existing ifNotNil: [^ self].
    stage addMorph: (list position: stage topRight - ((list width + 10)@0)).
    list startStepping' classified: 'list ops'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'hideList: listName
    | stage |
    stage := self ownerThatIsA: ScratchStageMorph.
    stage ifNil: [^ self].
    stage submorphs do: [:m |
        ((m isKindOf: ScratchListMorph) and: [
            m listName = listName and: [m target = self]]) ifTrue: [m delete]]' classified: 'list ops'.

"--- set/change attribute of a sprite or the stage --------------------"

(Smalltalk at: #ScriptableScratchMorph) compile: 'attributeTarget: aTarget
    | stage |
    aTarget isNil ifTrue: [^ self].
    aTarget = #myself ifTrue: [^ self].
    (aTarget isKindOf: ScriptableScratchMorph) ifTrue: [^ aTarget].
    (aTarget asString = ''Stage'') ifTrue: [
        ^ self ownerThatIsA: ScratchStageMorph].
    stage := self ownerThatIsA: ScratchStageMorph.
    stage ifNil: [^ nil].
    ^ stage submorphs detect: [:m |
        (m isKindOf: ScratchSpriteMorph) and: [
            m objName asString = aTarget asString]] ifNone: [nil]' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'setAttribute: attr of: aTarget to: value
    | obj a |
    obj := self attributeTarget: aTarget.
    obj ifNil: [^ self].
    a := attr asString.
    (obj isKindOf: ScratchSpriteMorph) ifTrue: [
        a = ''x position'' ifTrue: [^ obj xpos: value asNumberNoError].
        a = ''y position'' ifTrue: [^ obj ypos: value asNumberNoError].
        a = ''direction'' ifTrue: [^ obj heading: value asNumberNoError].
        a = ''costume #'' ifTrue: [^ obj costumeIndex: value asNumberNoError].
        a = ''costume name'' ifTrue: [^ obj lookLike: value asString].
        a = ''size'' ifTrue: [^ obj setSizeTo: value asNumberNoError]].
    a = ''volume'' ifTrue: [^ obj setVolumeTo: value asNumberNoError].
    a = ''background #'' ifTrue: [^ obj costumeIndex: value asNumberNoError].
    a = ''backdrop name'' ifTrue: [^ obj lookLike: value asString].
    ^ self' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'changeAttribute: attr of: aTarget by: delta
    | obj a n |
    obj := self attributeTarget: aTarget.
    obj ifNil: [^ self].
    a := attr asString.
    n := delta asNumberNoError.
    (obj isKindOf: ScratchSpriteMorph) ifTrue: [
        a = ''x position'' ifTrue: [^ obj changeXposBy: n].
        a = ''y position'' ifTrue: [^ obj changeYposBy: n].
        a = ''direction'' ifTrue: [^ obj heading: obj heading + n].
        a = ''costume #'' ifTrue: [^ obj costumeIndex: obj costumeIndex + n].
        a = ''size'' ifTrue: [^ obj changeSizeBy: n]].
    a = ''volume'' ifTrue: [^ obj changeVolumeBy: n].
    a = ''background #'' ifTrue: [^ obj changeBackgroundIndexBy: n].
    ^ self' classified: 'ai blocks'.

"--- stop other scripts in this sprite -------------------------------"

"Track the currently stepping ScratchProcess; only used by stopOtherScripts."
(Smalltalk at: #ScratchProcess) compile: 'runStepFor: aStageMorph
    | expr |
    Smalltalk at: #AIcurrentProcess put: self.
    readyToYield := false.
    [readyToYield or: [stackFrame isNil]] whileFalse: [
        self evaluateFor: aStageMorph].
    readyToTerminate ifTrue: [
        [stackFrame isNil] whileFalse: [
            expr := stackFrame expression.
            (expr isKindOf: BlockMorph) ifTrue: [expr litUp: false].
            self popStackFrame]]' classified: 'entry points'.

"Scratch 1.4.0 stores running scripts as blocks in runningBlocks; older
snapshots had a stage-level processes collection. processesToRun is the
supported accessor and returns a fresh collection."
(Smalltalk at: #ScratchStageMorph) compile: 'aiProcesses
    ^ self processesToRun' classified: 'ai blocks'.

"ScratchProcess has topBlock: setters but no getter."
(Smalltalk at: #ScratchProcess) compile: 'aiTopBlock
    ^ topBlock' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'stopOtherScripts
    | stage current |
    stage := self ownerThatIsA: ScratchStageMorph.
    stage ifNil: [^ self].
    current := Smalltalk at: #AIcurrentProcess ifAbsent: [nil].
    "includesReceiver: is useless in 1.4.0: ScratchStackFrame has no receiver,
    so it is always false. A process belongs to this sprite when its top block
    (the hat) has this sprite as scriptOwner."
    stage aiProcesses copy do: [:p |
        (p ~~ current and: [
            p aiTopBlock notNil and: [p aiTopBlock scriptOwner == self]])
            ifTrue: [p stop]]' classified: 'ai blocks'.

"--- any key ---------------------------------------------------------"

(Smalltalk at: #ScriptableScratchMorph) compile: 'keyNames
    ^ ((#(''any'' ''up arrow'' ''down arrow'' ''right arrow'' ''left arrow'' ''space''),
       ($a to: $z), ($0 to: $9)) collect: [:ch | ch asString])' classified: 'sensing ops'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'keyPressed: keyName
    | ch |
    keyName asString = ''any'' ifTrue: [
        0 to: 255 do: [:i | (Sensor keyPressed: i) ifTrue: [^ true]].
        ^ false].
    ch := self asciiFor: keyName.
    (Sensor keyPressed: ch) ifTrue: [^ true].
    (ch between: $a asciiValue and: $z asciiValue) ifTrue: [
        ^ Sensor keyPressed: ch - 32].
    (ch between: $A asciiValue and: $Z asciiValue) ifTrue: [
        ^ Sensor keyPressed: ch + 32].
    ^ false' classified: 'sensing ops'.

(Smalltalk at: #KeyEventHatMorph) compile: 'respondsToKeyEvent: aMorphicKeyEvent
    | evtAscii |
    scriptNameMorph choice asString = ''any'' ifTrue: [^ true].
    evtAscii := aMorphicKeyEvent keyCharacter asLowercase asciiValue.
    evtAscii = Character enter asciiValue ifTrue: [
        evtAscii := Character cr asciiValue].
    ^ evtAscii = (ScriptableScratchMorph new asciiFor: scriptNameMorph choice asString)' classified: 'other'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'goToBack
    ^ self layer: 1' classified: 'ai blocks'.

(Smalltalk at: #ScriptableScratchMorph) compile: 'goForwardByLayers: aNumber
    ^ self goBackByLayers: aNumber negated' classified: 'ai blocks'.

"Rebuild tuple lookup and refresh the palette."
(Smalltalk at: #ScriptableScratchMorph) buildBlockSpecDictionary.
(Smalltalk at: #AIHarness) logLine: 'block gaps loaded'.
