"Keep AI script ownership across project files.

The .sb format stores the workPane, not the harness registry. On save we write
<project>.sb.meta (id|label|target|hash per AI script). On open we clear the
stale registry, then re-associate scripts by content hash.

Load after 24_project_files.st."

(Smalltalk at: #AIChangeSetApplier) class compile: 'resetForProject
    Scripts := Dictionary new.
    Labels := Dictionary new.
    AppliedHashes := Dictionary new.
    UndoStack := OrderedCollection new.
    ^ self' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'registerScript: id label: aString stack: aStack
    self scripts at: id asString put: aStack.
    self labels at: id asString put: (aString ifNil: [id asString]).
    AppliedHashes ifNil: [AppliedHashes := Dictionary new].
    AppliedHashes at: id asString put: ((Smalltalk at: #AIHarness) perform: #hashForTuples: with: aStack tupleSequence).
    ^ self' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'idForHash: aString
    | hashes |
    AppliedHashes ifNil: [^ nil].
    AppliedHashes keysDo: [:id |
        (AppliedHashes at: id) = aString ifTrue: [^ id asString]].
    ^ nil' classified: 'registry'.

(Smalltalk at: #AIHarness) class compile: 'scriptContextFor: aHat
    | tuples hash id registry owned edited hatName label |
    tuples := aHat tupleSequence.
    hash := self hashForTuples: tuples.
    registry := (Smalltalk at: #AIChangeSetApplier) perform: #scripts.
    id := nil.
    registry keysDo: [:key | (registry at: key) == aHat ifTrue: [id := key asString]].
    id ifNil: [
        id := (Smalltalk at: #AIChangeSetApplier) perform: #idForHash: with: hash].
    owned := id notNil.
    hatName := (tuples first first) asString.
    label := hatName.
    owned
        ifTrue: [
            label := (Smalltalk at: #AIChangeSetApplier) perform: #labelFor: with: id.
            label ifNil: [label := hatName].
            edited := (Smalltalk at: #AIChangeSetApplier) perform: #userEditedId: with: id]
        ifFalse: [
            id := ''user-'', hash.
            label := ''original '', hatName.
            edited := false].
    ^ (OrderedCollection new
        add: id;
        add: label;
        add: hatName;
        add: tuples size;
        add: hash;
        add: owned;
        add: edited;
        yourself) asArray' classified: 'context'.

(Smalltalk at: #AIHarness) class compile: 'metaParts: line
    | p1 p2 p3 |
    p1 := line findString: ''|''.
    p1 = 0 ifTrue: [^ nil].
    p2 := line findString: ''|'' startingAt: p1 + 1.
    p2 = 0 ifTrue: [^ nil].
    p3 := line findString: ''|'' startingAt: p2 + 1.
    p3 = 0 ifTrue: [^ nil].
    ^ Array
        with: (line copyFrom: 1 to: p1 - 1)
        with: (line copyFrom: p1 + 1 to: p2 - 1)
        with: (line copyFrom: p2 + 1 to: p3 - 1)
        with: (line copyFrom: p3 + 1 to: line size)' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'writeRegistryMetaFor: path
    | applier meta out stream target label |
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
    out := path asString, ''.meta''.
    stream := [FileStream newFileNamed: out] ifError: [:e :r | nil].
    stream ifNil: [
        self logDevError: ''project meta'' text: ''cannot write '', out.
        ^ self].
    [stream nextPutAll: meta contents; close] ifError: [:e :r | nil].
    self logLine: ''project meta written '', out.
    ^ self' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'restoreRegistryForProject: path
    | applier metaPath text stream line parts hat frame stage byHash normalized |
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
            parts := self metaParts: line.
            parts ifNotNil: [
                hat := byHash at: (parts at: 4) ifAbsent: [nil].
                hat ifNotNil: [
                    applier perform: #registerScript:label:stack:
                        with: (parts at: 1) with: (parts at: 2) with: hat]]]].
    applier perform: #refresh.
    self logLine: ''registry restored for '', path asString.
    ^ self' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'reconcileRegistry
    | applier frame stage byHash registry |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNil: [^ self].
    frame := self findFrame.
    frame ifNil: [^ self].
    stage := frame workPane.
    stage ifNil: [^ self].
    byHash := Dictionary new.
    [stage scripts do: [:h |
        byHash at: (self hashForTuples: h tupleSequence) put: h]]
        ifError: [:e :r | nil].
    stage submorphs do: [:m |
        (m isKindOf: ScratchSpriteMorph) ifTrue: [
            [m scripts do: [:h |
                byHash at: (self hashForTuples: h tupleSequence) put: h]]
                ifError: [:e :r | nil]]].
    registry := applier perform: #scripts.
    registry keysDo: [:id | | stack hash visible |
        stack := registry at: id.
        hash := [self hashForTuples: stack tupleSequence] ifError: [:e :r | nil].
        hash ifNotNil: [
            visible := byHash at: hash ifAbsent: [nil].
            visible ifNotNil: [registry at: id put: visible]]].
    ^ self' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'apply: anArray
    | changes undo |
    (Smalltalk at: #AIHarness) perform: #reconcileRegistry.
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

(Smalltalk at: #AIHarness) class compile: 'openProject: path
    | frame stream |
    self logLine: ''project open '', path asString.
    frame := self findFrame.
    frame ifNil: [^ ''error: no frame''].
    path asString isEmpty ifTrue: [^ ''error: empty path''].
    stream := [FileStream readOnlyFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ ''error: cannot read '', path asString].
    [stream close] ifError: [:e :r | nil].
    [frame closeMediaEditorsAndDialogs] ifError: [:e :r | nil].
    [frame openScratchProjectNamed: path]
        ifError: [:e :r |
            self logDevError: ''project open'' text: path asString, '' -- '', e asString.
            ^ ''error: '', e asString].
    [self restoreRegistryForProject: path]
        ifError: [:e :r | self logDevError: ''registry restore'' text: e asString].
    self logLine: ''project opened '', path asString.
    ^ ''ok project open '', path asString' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'saveProject: path
    | frame stream |
    frame := self findFrame.
    frame ifNil: [^ ''error: no frame''].
    path asString isEmpty ifTrue: [^ ''error: empty path''].
    stream := [FileStream newFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ ''error: cannot write '', path asString].
    stream := [stream binary] ifError: [:e :r | stream].
    [frame writeScratchProjectOn: stream]
        ifError: [:e :r |
            [stream close] ifError: [:x :y | nil].
            self logDevError: ''project save'' text: path asString, '' -- '', e asString.
            ^ ''error: '', e asString].
    [stream close] ifError: [:e :r | nil].
    [self writeRegistryMetaFor: path]
        ifError: [:e :r | self logDevError: ''project meta'' text: e asString].
    self logLine: ''project saved '', path asString.
    ^ ''ok project save '', path asString' classified: 'project files'.

Transcript show: 'project registry sync installed'; cr.
