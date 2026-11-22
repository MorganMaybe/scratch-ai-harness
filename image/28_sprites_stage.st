"Sprites, stage scripts and backdrops.

Adds AIChangeSetApplier actions:
  createSprite  duplicateSprite  deleteSprite
  addCostume    setBackdrop     setSprite
and AI ownership persistence in the .meta sidecar.

Verified calls in this 2009 image (see scratch/base/probes/*.st):
  - ScratchSpriteMorph new soleCostume: media
  - ScratchFrameMorph addAndView: sprite   (registers in stage sprites, renames)
  - sprite objName: name                   (set AFTER addAndView:)
  - sprite xpos:/ypos:/heading:
  - sprite scalePoint: (percent / 100 @ percent / 100)   (scale is percent)
  - sprite visibility: 100|0
  - sprite rotationStyle: #normal | #leftRight | #none
  - stage addMediaItem:, stage lookLike: (backdrops)
  - stage sprites remove: sprite ifAbsent: []
  - sprite delete

Load after 27_text_project.st."

| classVars |
classVars := (Smalltalk at: #AIChangeSetApplier) classVarNames collect: [:s | s asString].
(classVars includes: 'SpriteOwners')
    ifFalse: [(Smalltalk at: #AIChangeSetApplier) addClassVarName: 'SpriteOwners'].

"--- ownership -----------------------------------------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'spriteOwners
    SpriteOwners ifNil: [SpriteOwners := Dictionary new].
    ^ SpriteOwners' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'resetSpriteOwners
    SpriteOwners := Dictionary new.
    ^ self' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'markSpriteOwned: aName
    self spriteOwners at: aName asString put: true.
    ^ self' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'unmarkSpriteOwned: aName
    self spriteOwners removeKey: aName asString ifAbsent: [].
    ^ self' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'spriteOwned: aName
    ^ self spriteOwners includesKey: aName asString' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'ownedSpriteNames
    ^ self spriteOwners keys asSortedCollection asArray' classified: 'sprites'.

"--- media ---------------------------------------------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'mediaRoot
    ^ FileDirectory default pathName, ''\Media\''' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'libraryPathFor: aString folder: aFolder
    | out |
    out := WriteStream on: String new.
    aString asString do: [:ch |
        ch = $/
            ifTrue: [out nextPut: $\]
            ifFalse: [out nextPut: ch]].
    ^ self mediaRoot, aFolder asString, ''\'', out contents' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'imageMediaFor: aLibrary folder: aFolder name: aName centerX: cx centerY: cy
    | form original scaled media p |
    form := [Form fromFileNamed: (self libraryPathFor: aLibrary folder: aFolder)]
        ifError: [:e :r | nil].
    form ifNil: [^ nil].
    original := form extent.
    scaled := [(Smalltalk at: #ScratchFrameMorph) scaledFormForPaintEditor: form]
        ifError: [:e :r | form].
    media := (Smalltalk at: #ImageMedia) new form: scaled.
    media name: aName asString.
    (cx notNil and: [cy notNil]) ifTrue: [
        "The bridge already converts Scratch 2.0 centers to bitmap pixels;
        only undo any paint-editor shrink here."
        p := ((cx * (scaled width / (original x max: 1))) rounded)
            @ ((cy * (scaled height / (original y max: 1))) rounded).
        p := ((p x max: 0) min: (scaled width - 1))
            @ ((p y max: 0) min: (scaled height - 1)).
        media rotationCenter: p].
    ^ media' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'imageMediaFor: aLibrary folder: aFolder name: aName
    ^ self imageMediaFor: aLibrary folder: aFolder name: aName centerX: nil centerY: nil
    ' classified: 'sprites'.

"The text importer was written against the block selector name; this image only
has the scalePoint: setter. Add the percent setter so text and .sprite paths
that say scale: keep working."
(Smalltalk at: #ScratchSpriteMorph) compile: 'scale: aNumber
    | fraction |
    fraction := aNumber asNumber / 100.0.
    ^ self scalePoint: (fraction @ fraction)' classified: 'accessing'.

"--- property helpers ---------------------------------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'rotationSymbolFor: aString
    | text |
    text := aString asString.
    text = ''left-right'' ifTrue: [^ #leftRight].
    text = ''don''''t rotate'' ifTrue: [^ #none].
    ^ #normal' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'rotationStringFor: aSymbol
    ^ aSymbol asString' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'spritePropsFor: aName
    | sprite |
    sprite := self targetNamed: aName.
    sprite ifNil: [^ nil].
    ^ Array
        with: sprite xpos
        with: sprite ypos
        with: sprite heading
        with: sprite scale
        with: (sprite visibility > 0)
        with: (self rotationStringFor: sprite rotationStyle)' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'setSprite: aSprite x: x y: y direction: direction size: size visible: visible rotation: rotation
    (aSprite isNil or: [aSprite isKindOf: ScratchStageMorph]) ifTrue: [^ nil].
    x ifNotNil: [aSprite xpos: x].
    y ifNotNil: [aSprite ypos: y].
    direction ifNotNil: [aSprite heading: direction].
    size ifNotNil: [
        size > 0 ifTrue: [
            aSprite scalePoint: ((size / 100.0) @ (size / 100.0))]].
    visible ifNotNil: [
        aSprite visibility: (visible ifTrue: [100] ifFalse: [0])].
    rotation ifNotNil: [
        aSprite rotationStyle: (self rotationSymbolFor: rotation)].
    ^ aSprite' classified: 'sprites'.

"--- applier actions ----------------------------------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'createSprite: aName costumes: costumeList x: x y: y direction: direction size: size visible: visible rotation: rotation
    | frame stage first media sprite |
    frame := self findFrame.
    frame ifNil: [^ nil].
    stage := frame workPane.
    stage ifNil: [^ nil].
    costumeList isEmpty ifTrue: [^ nil].
    first := costumeList at: 1.
    media := self imageMediaFor: (first at: 1) folder: ''Costumes'' name: (first at: 2)
        centerX: (first size > 2 ifTrue: [first at: 3] ifFalse: [nil])
        centerY: (first size > 3 ifTrue: [first at: 4] ifFalse: [nil]).
    media ifNil: [
        self reportProblem: ''cannot read costume '', (first at: 1) asString.
        ^ nil].
    sprite := (Smalltalk at: #ScratchSpriteMorph) new soleCostume: media.
    frame addAndView: sprite.
    sprite objName: aName asString.
    2 to: costumeList size do: [:i | | extra |
        extra := self imageMediaFor: ((costumeList at: i) at: 1)
            folder: ''Costumes'' name: ((costumeList at: i) at: 2)
            centerX: ((costumeList at: i) size > 2
                ifTrue: [(costumeList at: i) at: 3] ifFalse: [nil])
            centerY: ((costumeList at: i) size > 3
                ifTrue: [(costumeList at: i) at: 4] ifFalse: [nil]).
        extra ifNotNil: [sprite addMediaItem: extra]].
    sprite costumeIndex: 1.
    self setSprite: sprite x: x y: y direction: direction size: size
        visible: visible rotation: rotation.
    self markSpriteOwned: aName.
    [sprite viewBlocksAndScripts] ifError: [:e :r | nil].
    ^ sprite' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'deleteSprite: aName
    | sprite stage ids |
    sprite := self targetNamed: aName.
    sprite ifNil: [^ nil].
    (sprite isKindOf: ScratchSpriteMorph) ifFalse: [^ nil].
    stage := self stage.
    ids := OrderedCollection new.
    self scripts keysDo: [:id | | stack |
        stack := self scripts at: id.
        [(stack scriptOwner == sprite) ifTrue: [ids add: id]]
            ifError: [:e :r | nil]].
    ids do: [:id | self deleteScript: id].
    stage ifNotNil: [
        [stage sprites remove: sprite ifAbsent: []]
            ifError: [:e :r | nil]].
    sprite delete.
    self unmarkSpriteOwned: aName.
    ^ nil' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'duplicateSprite: sourceName as: newName
    | source frame sprite costumes |
    source := self targetNamed: sourceName.
    source ifNil: [^ nil].
    (source isKindOf: ScratchSpriteMorph) ifFalse: [^ nil].
    costumes := source costumeNames asArray.
    costumes isEmpty ifTrue: [^ nil].
    sprite := (Smalltalk at: #ScratchSpriteMorph) new
        soleCostume: ((source costumeFromName: (costumes at: 1)) deepCopy).
    frame := self findFrame.
    frame ifNil: [^ nil].
    frame addAndView: sprite.
    sprite objName: newName asString.
    2 to: costumes size do: [:i | | media |
        media := [(source costumeFromName: (costumes at: i)) deepCopy]
            ifError: [:e :r | nil].
        media ifNotNil: [sprite addMediaItem: media]].
    self setSprite: sprite
        x: source xpos y: source ypos direction: source heading
        size: source scale visible: (source visibility > 0)
        rotation: (self rotationStringFor: source rotationStyle).
    source allVarNames do: [:v | | value |
        value := [source getVar: v] ifError: [:e :r | 0].
        [sprite addVariable: v value: value] ifError: [:e :r | nil]].
    self markSpriteOwned: newName.
    [sprite viewBlocksAndScripts] ifError: [:e :r | nil].
    ^ sprite' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'addCostume: targetName library: aLibrary name: aName select: shouldSelect
    | target media |
    target := self targetNamed: targetName.
    target ifNil: [^ nil].
    media := self imageMediaFor: aLibrary folder: ''Costumes'' name: aName.
    media ifNil: [^ nil].
    [target addMediaItem: media] ifError: [:e :r | ^ nil].
    shouldSelect ifTrue: [
        [target lookLike: aName asString] ifError: [:e :r | nil]].
    ^ media' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'setBackdrop: aLibrary name: aName select: shouldSelect
    | stage media |
    stage := self stage.
    stage ifNil: [^ nil].
    media := self imageMediaFor: aLibrary folder: ''Backgrounds'' name: aName.
    media ifNil: [^ nil].
    [stage addMediaItem: media] ifError: [:e :r | ^ nil].
    shouldSelect ifTrue: [
        [stage lookLike: aName asString] ifError: [:e :r | nil]].
    ^ media' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'createList: name target: targetName items: itemList
    | target |
    target := self targetNamed: targetName.
    target ifNil: [
        self reportProblem: ''Unknown target: '', targetName asString.
        ^ nil].
    ([(target lists) includesKey: name] ifError: [:e :r | false])
        ifTrue: [
            self reportProblem: ''List already exists: '', name asString.
            ^ nil].
    [target createListNamed: name]
        ifError: [:e :r |
            self reportProblem: ''Cannot create list: '', e asString.
            ^ nil].
    itemList do: [:item |
        [target append: item toList: name] ifError: [:e :r | nil]].
    ^ nil' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'applyChange: change
    | action |
    action := change at: 1.
    ((action = #add) or: [action = #replace]) ifTrue: [
        (change size >= 5) ifTrue: [
            self recordLabel: (change at: 2) label: (change at: 5)]].
    action = #add ifTrue: [
        ^ self addScript: (change at: 2) target: (change at: 3) tuples: (change at: 4)].
    action = #replace ifTrue: [
        ^ self replaceScript: (change at: 2) target: (change at: 3) tuples: (change at: 4)].
    action = #delete ifTrue: [
        ^ self deleteScript: (change at: 2)].
    action = #createVariable ifTrue: [
        ^ self createVariable: (change at: 2) scope: (change at: 3) initial: (change at: 4)].
    action = #createList ifTrue: [
        ^ self createList: (change at: 2) target: (change at: 3) items: (change at: 4)].
    action = #createSprite ifTrue: [
        ^ self createSprite: (change at: 2) costumes: (change at: 3)
            x: (change at: 4) y: (change at: 5) direction: (change at: 6)
            size: (change at: 7) visible: (change at: 8) rotation: (change at: 9)].
    action = #duplicateSprite ifTrue: [
        ^ self duplicateSprite: (change at: 2) as: (change at: 3)].
    action = #deleteSprite ifTrue: [
        ^ self deleteSprite: (change at: 2)].
    action = #addCostume ifTrue: [
        ^ self addCostume: (change at: 2) library: (change at: 3)
            name: (change at: 4) select: (change at: 5)].
    action = #setBackdrop ifTrue: [
        ^ self setBackdrop: (change at: 2) name: (change at: 3) select: (change at: 4)].
    action = #setSprite ifTrue: [
        ^ self setSprite: (self targetNamed: (change at: 2))
            x: (change at: 3) y: (change at: 4) direction: (change at: 5)
            size: (change at: 6) visible: (change at: 7) rotation: (change at: 8)].
    ^ nil' classified: 'applying'.

"--- undo ----------------------------------------------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'costumeIndexFor: targetName
    | target |
    target := self targetNamed: targetName.
    target ifNil: [^ 1].
    ^ [target costumeIndex] ifError: [:e :r | 1]' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'spriteSpecFor: aName
    | sprite costumes vars scripts |
    sprite := self targetNamed: aName.
    sprite ifNil: [^ nil].
    costumes := OrderedCollection new.
    sprite costumeNames do: [:c | | media |
        media := [sprite costumeFromName: c] ifError: [:e :r | nil].
        media ifNotNil: [costumes add: (Array with: c with: media deepCopy)]].
    vars := OrderedCollection new.
    sprite allVarNames do: [:v | | value |
        value := [sprite getVar: v] ifError: [:e :r | 0].
        vars add: (Array with: v with: value)].
    scripts := OrderedCollection new.
    sprite scripts do: [:stack | | scriptId scriptLabel |
        scriptId := nil.
        self scripts keysDo: [:key |
            (self scripts at: key) == stack ifTrue: [scriptId := key asString]].
        scriptLabel := nil.
        scriptId ifNotNil: [
            scriptLabel := [self labelFor: scriptId] ifError: [:e :r | nil]].
        scripts add: (Array
            with: (scriptId ifNil: [''''])
            with: (scriptLabel ifNil: [''''])
            with: stack tupleSequence)].
    ^ Array
        with: aName
        with: costumes asArray
        with: (self spritePropsFor: aName)
        with: vars asArray
        with: scripts asArray' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'recreateSpriteFrom: spec
    | aName costumes props vars scripts frame sprite |
    spec ifNil: [^ nil].
    aName := spec at: 1.
    costumes := spec at: 2.
    props := spec at: 3.
    vars := spec at: 4.
    scripts := spec at: 5.
    costumes isEmpty ifTrue: [^ nil].
    sprite := (Smalltalk at: #ScratchSpriteMorph) new
        soleCostume: (((costumes at: 1) at: 2) deepCopy).
    frame := self findFrame.
    frame ifNil: [^ nil].
    frame addAndView: sprite.
    sprite objName: aName asString.
    2 to: costumes size do: [:i |
        sprite addMediaItem: (((costumes at: i) at: 2) deepCopy)].
    self setSprite: sprite
        x: (props at: 1) y: (props at: 2) direction: (props at: 3)
        size: (props at: 4) visible: (props at: 5) rotation: (props at: 6).
    vars do: [:pair |
        [sprite addVariable: (pair at: 1) value: (pair at: 2)]
            ifError: [:e :r | nil]].
    scripts do: [:record | | scriptId scriptLabel tuples stack |
        scriptId := (record at: 1) asString.
        scriptLabel := (record at: 2) asString.
        tuples := record at: 3.
        stack := [sprite stackFromTupleList: tuples receiver: sprite]
            ifError: [:e :r | nil].
        stack ifNotNil: [
            sprite addStack: stack.
            scriptId isEmpty ifFalse: [
                self registerScript: scriptId label: scriptLabel stack: stack]]].
    self markSpriteOwned: aName.
    ^ sprite' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'removeCostume: aName from: targetName
    | target media |
    target := self targetNamed: targetName.
    target ifNil: [^ nil].
    media := [target costumeFromName: aName] ifError: [:e :r | nil].
    media ifNotNil: [[target deleteMedia: media] ifError: [:e :r | nil]].
    ^ nil' classified: 'sprites'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'undoRecordFor: change
    | action id target old name label |
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
        label := [self labelFor: id] ifError: [:e :r | nil].
        ^ Array with: #delete with: id with: target
            with: (old ifNil: [nil] ifNotNil: [old tupleSequence])
            with: label].
    action = #createVariable ifTrue: [
        ^ Array with: #createVariable with: (change at: 2) with: (change at: 3)].
    action = #createList ifTrue: [
        ^ Array with: #deleteList with: (change at: 2) with: (change at: 3)].
    action = #createSprite ifTrue: [
        ^ Array with: #createSprite with: (change at: 2)].
    action = #deleteSprite ifTrue: [
        name := change at: 2.
        ^ Array with: #deleteSprite with: name with: (self spriteSpecFor: name)].
    action = #duplicateSprite ifTrue: [
        ^ Array with: #duplicateSprite with: (change at: 3)].
    action = #addCostume ifTrue: [
        name := change at: 4.
        ^ Array with: #addCostume with: (change at: 2) with: name
            with: (self costumeIndexFor: (change at: 2))
            with: ([(self targetNamed: (change at: 2)) costumeNames includes: name]
                ifError: [:e :r | false])].
    action = #setBackdrop ifTrue: [
        name := change at: 3.
        ^ Array with: #setBackdrop with: name
            with: ([self stage costumeIndex] ifError: [:e :r | 1])
            with: ([self stage costumeNames includes: name] ifError: [:e :r | false])].
    action = #setSprite ifTrue: [
        ^ Array with: #setSprite with: (change at: 2)
            with: (self spritePropsFor: (change at: 2))].
    ^ nil' classified: 'undo'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'undoRecord: record
    | action id target tuples props label existed |
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
        label := record size >= 5
            ifTrue: [record at: 5]
            ifFalse: [nil].
        self addScript: id target: target tuples: tuples.
        label ifNotNil: [self recordLabel: id label: label].
        ^ self scripts at: id ifAbsent: [nil]].
    action = #createVariable ifTrue: [
        target := (record at: 3) = #global
            ifTrue: [self stage]
            ifFalse: [self targetNamed: self currentTargetName].
        target ifNotNil: [target deleteVariable: (record at: 2)].
        ^ target].
    action = #deleteList ifTrue: [
        target := self targetNamed: (record at: 3).
        target ifNotNil: [
            [target deleteList: (record at: 2)] ifError: [:e :r | nil]].
        ^ target].
    action = #createSprite ifTrue: [
        ^ self deleteSprite: (record at: 2)].
    action = #deleteSprite ifTrue: [
        ^ self recreateSpriteFrom: (record at: 3)].
    action = #duplicateSprite ifTrue: [
        ^ self deleteSprite: (record at: 2)].
    action = #addCostume ifTrue: [
        existed := record size >= 5 ifTrue: [record at: 5] ifFalse: [false].
        existed ifFalse: [
            self removeCostume: (record at: 3) from: (record at: 2)].
        target := self targetNamed: (record at: 2).
        target ifNotNil: [
            [(record at: 4) > 0 ifTrue: [target costumeIndex: (record at: 4)]]
                ifError: [:e :r | nil]].
        ^ target].
    action = #setBackdrop ifTrue: [
        existed := record size >= 4 ifTrue: [record at: 4] ifFalse: [false].
        existed ifFalse: [
            self removeCostume: (record at: 2) from: ''Stage''].
        target := self stage.
        target ifNotNil: [
            [(record at: 3) > 0 ifTrue: [target costumeIndex: (record at: 3)]]
                ifError: [:e :r | nil]].
        ^ target].
    action = #setSprite ifTrue: [
        props := record at: 3.
        props ifNil: [^ nil].
        ^ self setSprite: (self targetNamed: (record at: 2))
            x: (props at: 1) y: (props at: 2) direction: (props at: 3)
            size: (props at: 4) visible: (props at: 5) rotation: (props at: 6)].
    ^ nil' classified: 'undo'.

"--- project registry / ownership persistence ---------------------------"
(Smalltalk at: #AIChangeSetApplier) class compile: 'resetForProject
    Scripts := Dictionary new.
    Labels := Dictionary new.
    AppliedHashes := Dictionary new.
    UndoStack := OrderedCollection new.
    self resetSpriteOwners.
    ^ self' classified: 'registry'.

(Smalltalk at: #AIHarness) class compile: 'metaSpriteParts: line
    | p1 p2 |
    p1 := line findString: ''|''.
    p1 = 0 ifTrue: [^ nil].
    p2 := line findString: ''|'' startingAt: p1 + 1.
    p2 = 0 ifTrue: [^ nil].
    ^ Array
        with: (line copyFrom: 1 to: p1 - 1)
        with: (line copyFrom: p1 + 1 to: p2 - 1)' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'writeRegistryMetaFor: path
    | applier meta out stream target label ownedNames |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNil: [^ self].
    meta := WriteStream on: String new.
    applier scripts keys asSortedCollection do: [:id |
        [(target := (applier scripts at: id) scriptOwner objName asString)
            ifNil: [target := '''']] ifError: [:e :r | target := ''''].
        [label := (applier perform: #labelFor: with: id) asString]
            ifError: [:e :r | label := id asString].
        meta nextPutAll: id asString, ''|'', label, ''|'', target, ''|'',
            (self hashForTuples: (applier scripts at: id) tupleSequence); nextPut: Character lf].
    ownedNames := [applier perform: #ownedSpriteNames] ifError: [:e :r | #()].
    ownedNames do: [:eachName |
        meta nextPutAll: ''sprite|'', eachName asString, ''|owned'';
            nextPut: Character lf].
    out := path asString, ''.meta''.
    stream := [FileStream newFileNamed: out] ifError: [:e :r | nil].
    stream ifNil: [
        self logDevError: ''project meta'' text: ''cannot write '', out.
        ^ self].
    [stream nextPutAll: meta contents; close] ifError: [:e :r | nil].
    self logLine: ''project meta written '', out.
    ^ self' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'restoreRegistryForProject: path
    | applier metaPath text stream line parts spriteParts hat frame stage byHash normalized |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNil: [^ self].
    applier perform: #resetForProject.
    frame := self findFrame.
    frame ifNil: [^ self].
    stage := frame workPane.
    stage ifNil: [^ self].
    byHash := Dictionary new.
    stage scripts do: [:h | byHash at: (self hashForTuples: h tupleSequence) put: h].
    stage submorphs do: [:m |
        (m isKindOf: ScratchSpriteMorph) ifTrue: [
            m scripts do: [:h | byHash at: (self hashForTuples: h tupleSequence) put: h]]].
    metaPath := path asString, ''.meta''.
    text := [((FileStream readOnlyFileNamed: metaPath) contentsOfEntireFile) asString]
        ifError: [:e :r | nil].
    text ifNil: [
        self logLine: ''no registry meta for '', path asString.
        ^ self].
    normalized := WriteStream on: String new.
    text do: [:ch |
        normalized nextPut: (ch = Character cr ifTrue: [Character lf] ifFalse: [ch])].
    stream := ReadStream on: normalized contents.
    [stream atEnd] whileFalse: [
        line := (stream upTo: Character lf) withBlanksTrimmed.
        line isEmpty ifFalse: [
            spriteParts := self metaSpriteParts: line.
            (spriteParts notNil and: [(spriteParts at: 1) = ''sprite'']) ifTrue: [
                applier perform: #markSpriteOwned: with: (spriteParts at: 2)]
            ifFalse: [
                parts := self metaParts: line.
                parts ifNotNil: [
                    hat := byHash at: (parts at: 4) ifAbsent: [nil].
                    hat ifNotNil: [
                        applier perform: #registerScript:label:stack:
                            with: (parts at: 1) with: (parts at: 2) with: hat]]]]].
    applier perform: #refresh.
    self logLine: ''registry restored for '', path asString.
    ^ self' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'restoreSpriteOwnersFromMetaFile: path
    | applier text stream line parts normalized |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNil: [^ self].
    text := [((FileStream readOnlyFileNamed: path) contentsOfEntireFile) asString]
        ifError: [:e :r | nil].
    text ifNil: [^ self].
    normalized := WriteStream on: String new.
    text do: [:ch |
        normalized nextPut: (ch = Character cr ifTrue: [Character lf] ifFalse: [ch])].
    stream := ReadStream on: normalized contents.
    [stream atEnd] whileFalse: [
        line := (stream upTo: Character lf) withBlanksTrimmed.
        line isEmpty ifFalse: [
            parts := self metaSpriteParts: line.
            (parts notNil and: [(parts at: 1) = ''sprite'']) ifTrue: [
                applier perform: #markSpriteOwned: with: (parts at: 2)]]].
    ^ self' classified: 'project files'.

"--- context: append the 8th sprite element -----------------------------"
(Smalltalk at: #AIHarness) class compile: 'spriteContextFor: aSprite
    | isStage vars lists costumes sounds scripts props |
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
    props := OrderedCollection new.
    isStage
        ifTrue: [
            props add: 0; add: 0; add: 90; add: 100; add: true;
                add: ''normal''; add: false]
        ifFalse: [
            props add: ([aSprite xpos] ifError: [:e :r | 0]);
                add: ([aSprite ypos] ifError: [:e :r | 0]);
                add: ([aSprite heading] ifError: [:e :r | 90]);
                add: ([aSprite scale] ifError: [:e :r | 100]);
                add: (([aSprite visibility] ifError: [:e :r | 100]) > 0);
                add: ([(Smalltalk at: #AIChangeSetApplier) perform: #rotationStringFor:
                        with: ([aSprite rotationStyle] ifError: [:e :r | #normal])]
                    ifError: [:e :r | ''normal'']);
                add: ([(Smalltalk at: #AIChangeSetApplier) perform: #spriteOwned:
                        with: aSprite objName] ifError: [:e :r | false])].
    props add: ([aSprite costumeIndex] ifError: [:e :r | 1]).
    ^ (OrderedCollection new
        add: aSprite objName asString;
        add: isStage;
        add: vars;
        add: lists;
        add: costumes;
        add: sounds;
        add: scripts asArray;
        add: props asArray;
        yourself) asArray' classified: 'context'.

"--- text import: restore sprite ownership ------------------------------"
(Smalltalk at: #AIHarness) class compile: 'exportCostumeIndex: aSprite to: dir file: fileName
    | path text index stream |
    index := [aSprite costumeIndex] ifError: [:e :r | 1].
    path := self textPath: dir file: fileName.
    text := self readTextFile: path.
    text ifNil: [^ self].
    stream := [FileStream newFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ self].
    [stream nextPutAll: text;
        nextPutAll: ''costumeIndex='', index printString; cr; close]
        ifError: [:e :r | nil].
    ^ self' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'applyTextCostumeIndex: text sprite: aSprite
    | tab |
    tab := String with: Character tab.
    (self textLines: text) do: [:line | | kv |
        (line findString: tab) = 0 ifTrue: [
            kv := self textKeyValue: line.
            (kv notNil and: [(kv at: 1) = ''costumeIndex'']) ifTrue: [
                [aSprite costumeIndex: (kv at: 2) asNumber]
                    ifError: [:e :r | nil]]]].
    ^ self' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'exportProjectText: dirArg
    | frame stage dir manifest sprites name file errors target |
    dir := dirArg asString.
    dir isEmpty ifTrue: [^ ''error: empty dir''].
    frame := self findFrame.
    frame ifNil: [^ ''error: no frame''].
    stage := frame workPane.
    stage ifNil: [^ ''error: no stage''].
    (dir last = $\ or: [dir last = $/]) ifTrue: [
        dir := dir copyFrom: 1 to: dir size - 1].
    manifest := WriteStream on: String new.
    manifest nextPutAll: ''format=scratch-ai-text/1''; cr.
    target := [self asyncTargetName] ifError: [:e :r | ''Stage''].
    manifest nextPutAll: ''target='', target; cr.
    errors := 0.
    sprites := OrderedCollection new.
    sprites add: stage.
    stage submorphs do: [:m |
        (m isKindOf: ScratchSpriteMorph) ifTrue: [sprites add: m]].
    sprites do: [:s | | result |
        name := s objName asString.
        file := ''sprite-'', (self safeFilePart: name), ''.txt''.
        manifest nextPutAll: ''sprite='', name; cr.
        result := [(self exportSpriteText: s to: dir file: file)
            ifNotNil: [errors := errors + 1]]
            ifError: [:e :r |
                errors := errors + 1.
                self logDevError: ''text export'' text: name, '' -- '', e asString.
                nil].
        [self exportCostumeIndex: s to: dir file: file]
            ifError: [:e :r | nil]].
    manifest nextPutAll: ''nextScriptId='', (self nextProjectScriptId); cr.
    (self writeText: manifest contents to: (self textPath: dir file: ''manifest.txt''))
        ifFalse: [^ ''error: cannot write manifest''].
    [self writeRegistryMetaFor: (self textPath: dir file: ''harness'')]
        ifError: [:e :r | nil].
    self logLine: ''project text exported '', dir.
    ^ ''ok project export '', dir, (errors > 0 ifTrue: ['' warnings='', errors printString] ifFalse: [''''])' classified: 'text project'.


(Smalltalk at: #AIHarness) class compile: 'importProjectText: dirArg
    | tpFrame tpStage tpDir tpManifest tpLines tpSpriteNames tpTargetName tpSprites tpApplier |
    tpDir := dirArg asString.
    tpDir isEmpty ifTrue: [^ ''error: empty dir''].
    tpFrame := self findFrame.
    tpFrame ifNil: [^ ''error: no frame''].
    tpStage := tpFrame workPane.
    tpStage ifNil: [^ ''error: no stage''].
    tpApplier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    tpApplier ifNil: [^ ''error: no applier''].
    tpApplier perform: #resetForProject.
    (tpDir last = $\ or: [tpDir last = $/]) ifTrue: [
        tpDir := tpDir copyFrom: 1 to: tpDir size - 1].
    tpManifest := self readTextFile: (self textPath: tpDir file: ''manifest.txt'').
    tpManifest ifNil: [^ ''error: cannot read manifest''].
    tpLines := self textLines: tpManifest.
    tpSpriteNames := OrderedCollection new.
    tpTargetName := ''Sprite1''.
    tpLines do: [:tpLine | | tpKv |
        tpKv := self textKeyValue: tpLine.
        tpKv ifNotNil: [
            (tpKv at: 1) = ''target'' ifTrue: [tpTargetName := tpKv at: 2].
            (tpKv at: 1) = ''sprite'' ifTrue: [tpSpriteNames add: (tpKv at: 2)]]].
    tpSpriteNames isEmpty ifTrue: [^ ''error: manifest has no sprites''].
    tpStage submorphs asOrderedCollection do: [:tpMorph |
        (tpMorph isKindOf: ScratchSpriteMorph) ifTrue: [
            (tpSpriteNames includes: tpMorph objName asString) ifFalse: [tpMorph delete]]].
    tpSprites := Dictionary new.
    tpSprites at: ''Stage'' put: tpStage.
    tpSpriteNames do: [:tpName | | tpSprite |
        (tpName asString = ''Stage'') ifFalse: [
            tpSprite := tpStage submorphs
                detect: [:tpMorph | (tpMorph isKindOf: ScratchSpriteMorph) and: [tpMorph objName asString = tpName]]
                ifNone: [nil].
            tpSprite ifNil: [
                tpSprite := (Smalltalk at: #ScratchSpriteMorph) new.
                tpSprite objName: tpName.
                tpStage addMorph: tpSprite].
            tpSprites at: tpName put: tpSprite]].
    tpSpriteNames do: [:tpName | | tpSprite tpFile tpSpriteText |
        tpSprite := tpSprites at: tpName ifAbsent: [nil].
        tpSprite ifNotNil: [
            tpFile := ''sprite-'', (self safeFilePart: tpName), ''.txt''.
            tpSpriteText := self readTextFile: (self textPath: tpDir file: tpFile).
            tpSpriteText ifNil: [
                self logDevError: ''text import'' text: ''missing '', tpFile]
                ifNotNil: [
                    [self importSpriteText: tpSpriteText sprite: tpSprite dir: tpDir]
                        ifError: [:e :r |
                            self logDevError: ''text import'' text: tpName, '' -- '', e asString].
                    [self applyTextCostumeIndex: tpSpriteText sprite: tpSprite]
                        ifError: [:e :r | nil]]]].
    self restoreSpriteOwnersFromMetaFile: (self textPath: tpDir file: ''harness.meta'').
    (tpSprites at: tpTargetName ifAbsent: [nil]) ifNotNil: [
        [[tpFrame scriptsPane target: (tpSprites at: tpTargetName ifAbsent: [nil])]
            ifError: [:e :r | nil]]].
    tpApplier perform: #refresh.
    self logLine: ''project text imported '', tpDir.
    ^ ''ok project import '', tpDir' classified: 'text project'.

"--- control / install --------------------------------------------------"
(Smalltalk at: #AIHarness) logLine: 'sprites and stage installed'.
Transcript show: 'sprites and stage installed'; cr.
