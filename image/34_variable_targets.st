"Target-aware create_variable and undo.

The change-set literal now carries the target sprite as the 5th element of
#createVariable. Older 4-element literals still work (they fall back to the
current target). This fixes sprite-scoped variables being created on whichever
sprite happened to be selected, and undo deleting them from the wrong sprite.

The undo methods delegate to the previously installed versions instead of
replacing them. An earlier version copied the 09_undo basis and therefore
erased the createSprite/deleteSprite/duplicateSprite/costume/backdrop undo
from 28_sprites_stage.st. Load this after 28_sprites_stage.st."

"--- creation -----------------------------------------------------------"

(Smalltalk at: #AIChangeSetApplier) class compile: 'createVariable: name scope: scope initial: initial target: targetName
    | target scopeName |
    scopeName := scope asString.
    target := (scopeName = ''global'')
        ifTrue: [self stage]
        ifFalse: [self targetNamed: targetName].
    target ifNil: [^ nil].
    target addVariable: name.
    target setVar: name to: initial.
    ^ target' classified: 'applying'.

(Smalltalk at: #AIChangeSetApplier) class compile: 'createVariable: name scope: scope initial: initial
    ^ self createVariable: name scope: scope initial: initial
        target: self currentTargetName' classified: 'applying'.

((Smalltalk at: #AIChangeSetApplier) class includesSelector: #baseVariableApplyChange:) ifFalse: [
    (Smalltalk at: #AIChangeSetApplier) class methodDict
        at: #baseVariableApplyChange:
        put: ((Smalltalk at: #AIChangeSetApplier) class methodDict at: #applyChange:)].
(Smalltalk at: #AIChangeSetApplier) class compile: 'applyChange: change
    | action |
    action := change at: 1.
    action = #createVariable ifTrue: [
        ^ (change size >= 5)
            ifTrue: [
                self createVariable: (change at: 2) scope: (change at: 3)
                    initial: (change at: 4) target: (change at: 5)]
            ifFalse: [
                self createVariable: (change at: 2) scope: (change at: 3)
                    initial: (change at: 4)]].
    ^ self baseVariableApplyChange: change' classified: 'applying'.

"--- undo ---------------------------------------------------------------"

"Keep the currently installed implementations (28_sprites_stage.st in the
normal load order) and delegate everything except target-aware createVariable."
((Smalltalk at: #AIChangeSetApplier) class includesSelector: #baseVariableUndoRecordFor:) ifFalse: [
    (Smalltalk at: #AIChangeSetApplier) class methodDict
        at: #baseVariableUndoRecordFor:
        put: ((Smalltalk at: #AIChangeSetApplier) class methodDict at: #undoRecordFor:)].
(Smalltalk at: #AIChangeSetApplier) class compile: 'undoRecordFor: change
    | action |
    action := change at: 1.
    action = #createVariable ifTrue: [
        ^ Array with: #createVariable with: (change at: 2)
            with: (change at: 3)
            with: ((change size >= 5)
                ifTrue: [change at: 5]
                ifFalse: [self currentTargetName])].
    ^ self baseVariableUndoRecordFor: change' classified: 'undo'.

((Smalltalk at: #AIChangeSetApplier) class includesSelector: #baseVariableUndoRecord:) ifFalse: [
    (Smalltalk at: #AIChangeSetApplier) class methodDict
        at: #baseVariableUndoRecord:
        put: ((Smalltalk at: #AIChangeSetApplier) class methodDict at: #undoRecord:)].
(Smalltalk at: #AIChangeSetApplier) class compile: 'undoRecord: record
    | action target |
    action := record at: 1.
    action = #createVariable ifTrue: [
        target := (record at: 3) = #global
            ifTrue: [self stage]
            ifFalse: [
                self targetNamed: ((record size >= 4)
                    ifTrue: [record at: 4]
                    ifFalse: [self currentTargetName])].
        target ifNotNil: [target deleteVariable: (record at: 2)].
        ^ target].
    ^ self baseVariableUndoRecord: record' classified: 'undo'.

(Smalltalk at: #AIHarness) logLine: 'target-aware variables loaded'.
