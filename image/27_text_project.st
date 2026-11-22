"Git-diffable text project format (export + import).

Layout:
    <dir>/manifest.txt            format, target, sprite list, next id
    <dir>/sprite-<name>.txt       properties, vars, lists, scripts
    <dir>/costume-<sprite>-<name>.png
    <dir>/sound-<sprite>-<name>.wav
    <dir>/harness.meta            id|label|target|hash sidecar

The .sb file remains the runtime interchange; this format is for review, git
and scripts. Import replaces the scripts, variables, lists and media of each
sprite named in the manifest, and creates missing sprites. Keep .sb for assets
that this old VM cannot reconstruct from text alone.

Load after 26_async_send.st."

"Symbols are a String subclass in this image, so literalFor: must test Symbol
before String or block selectors are emitted as quoted strings."
(Smalltalk at: #AIHarness) class compile: 'literalFor: anObject
    | out |
    (anObject isKindOf: Array) ifTrue: [
        out := WriteStream on: String new.
        out nextPutAll: ''#(''.
        anObject do: [:each | out nextPutAll: (self literalFor: each); nextPut: $ ].
        out nextPut: $).
        ^ out contents].
    (anObject isKindOf: Symbol) ifTrue: [^ ''#'', anObject asString].
    (anObject isKindOf: String) ifTrue: [^ self literalString: anObject asString].
    anObject ifNil: [^ ''nil''].
    ((anObject isKindOf: Boolean) or: [anObject isKindOf: Number])
        ifTrue: [^ anObject printString].
    ^ self literalString: anObject asString' classified: 'text project'.

"Hashes written by earlier sessions treated symbols as strings (Symbol is a
String subclass and the old literalFor: tested String first). Keep hashing on
that canonical form so existing AppliedHashes and .meta files still restore,
while tuple serialization uses the corrected literalFor: above."
(Smalltalk at: #AIHarness) class compile: 'hashLiteralFor: anObject
    | out |
    (anObject isKindOf: Array) ifTrue: [
        out := WriteStream on: String new.
        out nextPutAll: ''#(''.
        anObject do: [:each | out nextPutAll: (self hashLiteralFor: each); nextPut: $ ].
        out nextPut: $).
        ^ out contents].
    (anObject isKindOf: String) ifTrue: [^ self literalString: anObject asString].
    (anObject isKindOf: Symbol) ifTrue: [^ ''#'', anObject asString].
    anObject ifNil: [^ ''nil''].
    ((anObject isKindOf: Boolean) or: [anObject isKindOf: Number])
        ifTrue: [^ anObject printString].
    ^ self literalString: anObject asString' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'hashForTuples: tupleList
    | text h |
    text := self hashLiteralFor: tupleList.
    h := 0.
    text do: [:ch | h := (h * 31 + ch asInteger) \\ 1000000007].
    ^ h printString' classified: 'text project'.

"ScratchMedia exposes name but no setter; a text import needs to preserve media
names, so add a small accessor."
(Smalltalk at: #ScratchMedia) compile: 'name: aString
    mediaName := aString asString.
    ^ self' classified: 'accessing'.

(Smalltalk at: #AIHarness) class compile: 'textPath: dir file: fileName
    ^ dir asString, ''\'', fileName asString' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'safeFilePart: aString
    | out bad |
    bad := ''\/:*?"<>| ''.
    out := WriteStream on: String new.
    aString asString do: [:ch |
        (bad includes: ch)
            ifTrue: [out nextPut: $_]
            ifFalse: [out nextPut: ch]].
    ^ out contents' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'textLines: text
    | out normalized stream line |
    normalized := WriteStream on: String new.
    text asString do: [:ch |
        normalized nextPut: (ch = Character cr ifTrue: [Character lf] ifFalse: [ch])].
    out := OrderedCollection new.
    stream := ReadStream on: normalized contents.
    [stream atEnd] whileFalse: [
        line := stream upTo: Character lf.
        line isEmpty ifFalse: [out add: line]].
    ^ out asArray' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'textTabs: aString
    | parts start idx tab done |
    tab := String with: Character tab.
    parts := OrderedCollection new.
    start := 1.
    done := false.
    [done] whileFalse: [
        idx := aString findString: tab startingAt: start.
        idx = 0
            ifTrue: [
                start > aString size
                    ifTrue: [parts add: '''']
                    ifFalse: [parts add: (aString copyFrom: start to: aString size)].
                done := true]
            ifFalse: [
                parts add: (aString copyFrom: start to: idx - 1).
                start := idx + 1]].
    ^ parts asArray' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'textKeyValue: aString
    | eq |
    eq := aString findString: ''=''.
    eq = 0 ifTrue: [^ nil].
    ^ Array with: (aString copyFrom: 1 to: eq - 1)
        with: (aString copyFrom: eq + 1 to: aString size)' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'parseTextLiteral: aString
    ^ [(Smalltalk at: #AILiteralReader) parse: aString asString]
        ifError: [:e :r | nil]' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'symbolizeTuple: anArray
    | out first |
    (anArray isKindOf: Array) ifFalse: [^ anArray].
    anArray isEmpty ifTrue: [^ anArray].
    first := anArray at: 1.
    (first isKindOf: Array) ifTrue: [
        out := OrderedCollection new.
        anArray do: [:each | out add: (self symbolizeTuple: each)].
        ^ out asArray].
    (first isKindOf: String) ifTrue: [
        out := OrderedCollection new.
        out add: first asSymbol.
        2 to: anArray size do: [:i | | each |
            each := anArray at: i.
            (each isKindOf: Array)
                ifTrue: [out add: (self symbolizeTuple: each)]
                ifFalse: [out add: each]].
        ^ out asArray].
    ^ anArray' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'writeText: text to: path
    | stream ok |
    [FileDirectory default deleteFileNamed: path] ifError: [:e :r | nil].
    stream := [FileStream newFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ false].
    ok := [stream nextPutAll: text asString.
        stream close.
        true]
        ifError: [:e :r |
            [stream close] ifError: [:e2 :r2 | nil].
            false].
    ^ ok' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'readTextFile: path
    | stream fileText |
    stream := [FileStream readOnlyFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ nil].
    fileText := [stream contentsOfEntireFile] ifError: [:e :r | nil].
    [stream close] ifError: [:e :r | nil].
    ^ fileText ifNil: [nil] ifNotNil: [fileText asString]' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'nextProjectScriptId
    | applier max n idString |
    max := 0.
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    applier ifNotNil: [
        (applier perform: #scripts) keysDo: [:id |
            idString := id asString.
            ((idString size > 3) and: [(idString copyFrom: 1 to: 3) = ''ai-'']) ifTrue: [
                n := [(idString copyFrom: 4 to: idString size) asNumber]
                    ifError: [:e :r | 0].
                n > max ifTrue: [max := n]]]].
    ^ ''ai-'', (max + 1) printString' classified: 'text project'.

"--- export ---------------------------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'exportSpriteText: aSprite to: dir file: fileName
    | out name isStage outPath tab listNames |
    tab := String with: Character tab.
    name := aSprite objName asString.
    isStage := aSprite isKindOf: ScratchStageMorph.
    out := WriteStream on: String new.
    out nextPutAll: ''name='', name; cr.
    out nextPutAll: ''isStage='', isStage printString; cr.
    isStage ifFalse: [
        out nextPutAll: ''x='', ([aSprite xpos] ifError: [:e :r | 0]) printString; cr.
        out nextPutAll: ''y='', ([aSprite ypos] ifError: [:e :r | 0]) printString; cr.
        out nextPutAll: ''heading='', ([aSprite heading] ifError: [:e :r | 90]) printString; cr.
        out nextPutAll: ''scale='', ([aSprite scale] ifError: [:e :r | 100]) printString; cr.
        out nextPutAll: ''rotationStyle='', ([aSprite rotationStyle] ifError: [:e :r | #normal]) asString; cr].
    out nextPutAll: ''visibility='', ([aSprite visibility] ifError: [:e :r | 100]) printString; cr.
    listNames := [(aSprite listVarNames) asArray collect: [:n | n asString]]
        ifError: [:e :r | #()].
    aSprite allVarNames asArray do: [:vName | | v |
        (listNames includes: vName asString) ifFalse: [
            v := [aSprite getVar: vName] ifError: [:e :r | nil].
            out nextPutAll: ''var''; nextPut: Character tab; nextPutAll: vName asString;
                nextPut: Character tab; nextPutAll: (self literalFor: v); cr]].
    aSprite listVarNames asArray do: [:lName | | list |
        list := [aSprite listNamed: lName ifNone: [nil]] ifError: [:e :r | nil].
        list ifNotNil: [
            out nextPutAll: ''list''; nextPut: Character tab; nextPutAll: lName asString;
                nextPut: Character tab; nextPutAll: (self literalFor: list asArray); cr]].
    aSprite scripts do: [:hat | | ctx id label tuples |
        ctx := self scriptContextFor: hat.
        id := (ctx at: 1) asString.
        label := (ctx at: 2) asString.
        tuples := hat tupleSequence.
        out nextPutAll: ''script''; nextPut: Character tab; nextPutAll: id;
            nextPut: Character tab; nextPutAll: label; nextPut: Character tab;
            nextPutAll: (self literalFor: (self symbolizeTuple: tuples)); cr].
    aSprite costumeNames asArray do: [:cName | | media form pngFile bmpFile pngPath bmpPath center |
        media := [aSprite costumeFromName: cName] ifError: [:e :r | nil].
        media ifNotNil: [
            form := [media form] ifError: [:e :r | nil].
            form ifNotNil: [
                pngFile := ''costume-'', (self safeFilePart: name), ''-'',
                    (self safeFilePart: cName), ''.png''.
                bmpFile := ''costume-'', (self safeFilePart: name), ''-'',
                    (self safeFilePart: cName), ''.bmp''.
                pngPath := self textPath: dir file: pngFile.
                bmpPath := self textPath: dir file: bmpFile.
                [FileDirectory default deleteFileNamed: pngPath] ifError: [:e :r | nil].
                [FileDirectory default deleteFileNamed: bmpPath] ifError: [:e :r | nil].
                [form writePNGFileNamed: pngPath] ifError: [:e :r | nil].
                [form writeBMPFileNamed: bmpPath] ifError: [:e :r | nil].
                center := [media rotationCenter] ifError: [:e :r | 0 @ 0].
                out nextPutAll: ''costume''; nextPut: Character tab;
                    nextPutAll: cName asString; nextPut: Character tab;
                    nextPutAll: pngFile; nextPut: Character tab;
                    nextPutAll: bmpFile; nextPut: Character tab;
                    nextPutAll: (center x) printString; nextPut: Character tab;
                    nextPutAll: (center y) printString; cr]]].
    aSprite soundNames asArray do: [:sName | | media snd file soundPath |
        (sName asString = ''-'') ifFalse: [
            media := [aSprite soundNamed: sName ifAbsent: [nil]] ifError: [:e :r | nil].
            media ifNotNil: [
                snd := [media sound] ifError: [:e :r | nil].
                snd ifNotNil: [
                    file := ''sound-'', (self safeFilePart: name), ''-'',
                        (self safeFilePart: sName), ''.wav''.
                    soundPath := self textPath: dir file: file.
                    [FileDirectory default deleteFileNamed: soundPath] ifError: [:e :r | nil].
                    [snd storeWAVOnFileNamed: soundPath] ifError: [:e :r | nil].
                    out nextPutAll: ''sound''; nextPut: Character tab;
                        nextPutAll: sName asString; nextPut: Character tab;
                        nextPutAll: file; cr]]]].
    outPath := self textPath: dir file: fileName.
    (self writeText: out contents to: outPath)
        ifFalse: [^ ''error: cannot write '', outPath].
    ^ nil' classified: 'text project'.

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
                nil]].
    manifest nextPutAll: ''nextScriptId='', (self nextProjectScriptId); cr.
    (self writeText: manifest contents to: (self textPath: dir file: ''manifest.txt''))
        ifFalse: [^ ''error: cannot write manifest''].
    [self writeRegistryMetaFor: (self textPath: dir file: ''harness'')]
        ifError: [:e :r | nil].
    self logLine: ''project text exported '', dir.
    ^ ''ok project export '', dir, (errors > 0 ifTrue: ['' warnings='', errors printString] ifFalse: [''''])' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'realSoundNamesIn: aSprite
    | names |
    names := [(aSprite soundNames) asArray] ifError: [:e :r | #()].
    ^ names select: [:each | | soundName |
        soundName := each asString.
        (soundName = ''-'') not and: [(soundName findString: ''record'') = 0]]' classified: 'text project'.

"--- import ---------------------------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'importCostumeRecord: p index: i sprite: aSprite dir: dir existing: existingCostumes
    | cName pngFile bmpFile form media cx cy |
    cName := p at: 2.
    pngFile := p at: 3.
    bmpFile := nil.
    cx := 0.
    cy := 0.
    p size >= 6
        ifTrue: [
            bmpFile := p at: 4.
            cx := [(p at: 5) asNumber] ifError: [:e :r | 0].
            cy := [(p at: 6) asNumber] ifError: [:e :r | 0]]
        ifFalse: [
            (p size >= 4) ifTrue: [
                cx := [(p at: 4) asNumber] ifError: [:e :r | 0].
                cy := [(p at: 5) asNumber] ifError: [:e :r | 0]]].
    form := nil.
    bmpFile ifNotNil: [
        form := [Form fromFileNamed: (self textPath: dir file: bmpFile)] ifError: [:e :r | nil]].
    form ifNil: [
        form := [Form fromFileNamed: (self textPath: dir file: pngFile)] ifError: [:e :r | nil]].
    form ifNil: [
        self logDevError: ''text import costume'' text: ''cannot read '', cName.
        ^ self].
    i <= existingCostumes size
        ifTrue: [media := [aSprite costumeFromName: (existingCostumes at: i)] ifError: [:e :r | nil]]
        ifFalse: [media := (Smalltalk at: #ImageMedia) new].
    media ifNil: [^ self].
    media form: form.
    media rotationCenter: cx @ cy.
    media name: cName.
    (i <= existingCostumes size) ifFalse: [
        [aSprite addMediaItem: media] ifError: [:e :r |
            self logDevError: ''text import costume'' text: cName, '' -- '', e asString]].
    ^ self' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'importSoundRecord: p index: i sprite: aSprite dir: dir existing: existingSounds
    | sName file path stream snd media |
    sName := p at: 2.
    file := p at: 3.
    path := self textPath: dir file: file.
    stream := [FileStream readOnlyFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ self].
    [stream binary] ifError: [:e :r | nil].
    snd := [(Smalltalk at: #SampledSound) readWAVFrom: stream] ifError: [:e :r | nil].
    [stream close] ifError: [:e :r | nil].
    snd ifNil: [^ self].
    i <= existingSounds size
        ifTrue: [media := [aSprite soundNamed: (existingSounds at: i) ifAbsent: [nil]] ifError: [:e :r | nil]]
        ifFalse: [media := (Smalltalk at: #SoundMedia) new].
    media ifNil: [^ self].
    media sound: snd.
    media name: sName.
    (i <= existingSounds size) ifFalse: [
        [aSprite addMediaItem: media] ifError: [:e :r |
            self logDevError: ''text import sound'' text: sName, '' -- '', e asString]].
    ^ self' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'importScriptRecord: p sprite: aSprite
    | id label tuple stack isUser |
    id := (p at: 2) asString.
    label := (p at: 3) asString.
    tuple := self parseTextLiteral: (p at: 4).
    tuple ifNil: [^ self].
    tuple := self symbolizeTuple: tuple.
    stack := [aSprite stackFromTupleList: tuple receiver: aSprite] ifError: [:e :r | nil].
    stack ifNil: [^ self].
    aSprite addStack: stack.
    isUser := (id size >= 5) and: [(id copyFrom: 1 to: 5) = ''user-''].
    isUser ifFalse: [
        (Smalltalk at: #AIChangeSetApplier) perform: #registerScript:label:stack:
            with: id with: label with: stack].
    ^ self' classified: 'text project'.

(Smalltalk at: #AIHarness) class compile: 'importSpriteText: text sprite: aSprite dir: dir
    | lines props scripts vars lists costumes sounds objName tab existingCostumes existingSounds |
    tab := String with: Character tab.
    props := Dictionary new.
    scripts := OrderedCollection new.
    vars := OrderedCollection new.
    lists := OrderedCollection new.
    costumes := OrderedCollection new.
    sounds := OrderedCollection new.
    lines := self textLines: text.
    lines do: [:line | | kv parts key |
        (line findString: tab) > 0
            ifTrue: [
                parts := self textTabs: line.
                parts size > 1 ifTrue: [
                    key := parts at: 1.
                    key = ''var'' ifTrue: [vars add: parts].
                    key = ''list'' ifTrue: [lists add: parts].
                    key = ''script'' ifTrue: [scripts add: parts].
                    key = ''costume'' ifTrue: [costumes add: parts].
                    key = ''sound'' ifTrue: [sounds add: parts]]]
            ifFalse: [
                kv := self textKeyValue: line.
                kv ifNotNil: [props at: (kv at: 1) put: (kv at: 2)]]].
    objName := props at: ''name'' ifAbsent: [nil].
    objName ifNotNil: [[aSprite objName: objName] ifError: [:e :r | nil]].
    (aSprite isKindOf: ScratchStageMorph) ifFalse: [
        (props at: ''x'' ifAbsent: [nil]) ifNotNil: [
            [aSprite xpos: (props at: ''x'') asNumber] ifError: [:e :r | nil]].
        (props at: ''y'' ifAbsent: [nil]) ifNotNil: [
            [aSprite ypos: (props at: ''y'') asNumber] ifError: [:e :r | nil]].
        (props at: ''heading'' ifAbsent: [nil]) ifNotNil: [
            [aSprite heading: (props at: ''heading'') asNumber] ifError: [:e :r | nil]].
        (props at: ''scale'' ifAbsent: [nil]) ifNotNil: [
            [aSprite scale: (props at: ''scale'') asNumber] ifError: [:e :r | nil]].
        (props at: ''rotationStyle'' ifAbsent: [nil]) ifNotNil: [
            [aSprite rotationStyle: (props at: ''rotationStyle'') asSymbol]
                ifError: [:e :r | nil]]].
    (props at: ''visibility'' ifAbsent: [nil]) ifNotNil: [
        [aSprite visibility: (props at: ''visibility'') asNumber]
            ifError: [:e :r | nil]].
    aSprite scripts asOrderedCollection do: [:h | h delete].
    aSprite allVarNames asArray do: [:n |
        [aSprite deleteVariable: n] ifError: [:e :r | nil]].
    vars do: [:p | | vName value |
        vName := p at: 2.
        value := self parseTextLiteral: (p at: 3).
        [aSprite addVariable: vName value: value] ifError: [:e :r |
            self logDevError: ''text import var'' text: vName, '' -- '', e asString]].
    aSprite listVarNames asArray do: [:n |
        [aSprite deleteList: n] ifError: [:e :r |
            [(aSprite lists) removeKey: n ifAbsent: []] ifError: [:e2 :r2 | nil]]].
    lists do: [:p | | lName value list |
        lName := p at: 2.
        value := self parseTextLiteral: (p at: 3).
        list := OrderedCollection new.
        (value isKindOf: Array) ifTrue: [value do: [:v | list add: v]].
        [aSprite lists at: lName put: list] ifError: [:e :r |
            self logDevError: ''text import list'' text: lName, '' -- '', e asString]].
    existingCostumes := [(aSprite costumeNames) asArray] ifError: [:e :r | #()].
    1 to: costumes size do: [:i |
        self importCostumeRecord: (costumes at: i) index: i sprite: aSprite
            dir: dir existing: existingCostumes].
    (costumes size < existingCostumes size) ifTrue: [
        ((costumes size + 1) to: existingCostumes size) do: [:i | | media |
            media := [aSprite costumeFromName: (existingCostumes at: i)] ifError: [:e :r | nil].
            media ifNotNil: [[aSprite deleteMedia: media] ifError: [:e :r | nil]]]].
    existingSounds := self realSoundNamesIn: aSprite.
    1 to: sounds size do: [:i |
        self importSoundRecord: (sounds at: i) index: i sprite: aSprite
            dir: dir existing: existingSounds].
    (sounds size < existingSounds size) ifTrue: [
        ((sounds size + 1) to: existingSounds size) do: [:i | | media |
            media := [aSprite soundNamed: (existingSounds at: i) ifAbsent: [nil]] ifError: [:e :r | nil].
            media ifNotNil: [[aSprite deleteMedia: media] ifError: [:e :r | nil]]]].
    costumes isEmpty ifFalse: [
        [aSprite costumeIndex: 1] ifError: [:e :r | nil]].
    scripts do: [:p | self importScriptRecord: p sprite: aSprite].
    aSprite viewBlocksAndScripts.
    ^ self' classified: 'text project'.

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
                            self logDevError: ''text import'' text: tpName, '' -- '', e asString]]]].
    (tpSprites at: tpTargetName ifAbsent: [nil]) ifNotNil: [
        [[tpFrame scriptsPane target: (tpSprites at: tpTargetName ifAbsent: [nil])]
            ifError: [:e :r | nil]]].
    tpApplier perform: #refresh.
    self logLine: ''project text imported '', tpDir.
    ^ ''ok project import '', tpDir' classified: 'text project'.

Transcript show: 'text project format installed'; cr.
