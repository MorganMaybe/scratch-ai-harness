"Persist script labels in the image so the project context the bridge sees
carries meaning ('draw_hexagon') instead of only 'EventHatMorph'. The bridge
already sends the label as the 5th element of #add/#replace change arrays."

| classVars |
classVars := (Smalltalk at: #AIChangeSetApplier) classVarNames collect: [:s | s asString].
(classVars includes: 'Labels')
    ifFalse: [(Smalltalk at: #AIChangeSetApplier) addClassVarName: 'Labels'].

(Smalltalk at: #AIChangeSetApplier) class compile: 'labels
    Labels ifNil: [Labels := Dictionary new].
    ^ Labels' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'labelFor: id
    Labels ifNil: [^ nil].
    ^ Labels at: id ifAbsent: [nil]' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'recordLabel: id label: aString
    (id isNil or: [aString isNil]) ifTrue: [^ nil].
    self labels at: id asString put: aString asString.
    ^ aString' classified: 'registry'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'applyChange: change
    | action id |
    action := change at: 1.
    id := change at: 2.
    ((action = #add) or: [action = #replace]) ifTrue: [
        (change size >= 5) ifTrue: [self recordLabel: id label: (change at: 5)]].
    action = #add ifTrue: [
        ^ self addScript: id target: (change at: 3) tuples: (change at: 4)].
    action = #replace ifTrue: [
        ^ self replaceScript: id target: (change at: 3) tuples: (change at: 4)].
    action = #delete ifTrue: [
        ^ self deleteScript: id].
    action = #createVariable ifTrue: [
        ^ self createVariable: (change at: 2) scope: (change at: 3) initial: (change at: 4)].
    ^ nil' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'deleteScript: id
    | old |
    old := self scripts at: id ifAbsent: [nil].
    old ifNil: [^ nil].
    old delete.
    self scripts removeKey: id ifAbsent: [].
    AppliedHashes ifNotNil: [AppliedHashes removeKey: id ifAbsent: []].
    Labels ifNotNil: [Labels removeKey: id ifAbsent: []].
    ^ nil' classified: 'applying'.

(Smalltalk at: #AIHarness) class compile: 'scriptContextFor: aHat
    | tuples hash id registry owned edited hatName label |
    tuples := aHat tupleSequence.
    hash := self hashForTuples: tuples.
    registry := (Smalltalk at: #AIChangeSetApplier) perform: #scripts.
    id := nil.
    registry keysDo: [:key | (registry at: key) == aHat ifTrue: [id := key asString]].
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

"Seed labels for the three scripts created before label tracking existed."
(Smalltalk at: #AIChangeSetApplier) perform: #recordLabel:label: with: 'ai-1' with: 'draw_square_done'.
(Smalltalk at: #AIChangeSetApplier) perform: #recordLabel:label: with: 'ai-2' with: 'draw_square'.
(Smalltalk at: #AIChangeSetApplier) perform: #recordLabel:label: with: 'ai-3' with: 'draw_hexagon'.
Transcript show: 'script labels installed'; cr.
