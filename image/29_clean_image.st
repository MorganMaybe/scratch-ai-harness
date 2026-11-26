"Clean-image maintenance.

The user keeps a 'latest, clean' image: the current harness classes, no
scripts, no pen trails, a cleared chat log, and only the cat (Sprite1). Use it
after each change set of work:

    python tools\ai_control.py load image\29_clean_image.st   (once per image)
    python tools\ai_control.py save-clean ScratchAiTesting

or the wrapper:

    .\tools\make_clean_image.ps1

`save-clean` cleans first, then saves under the requested name. If that name is
already the running image it snapshots in place; otherwise it removes stale
files of that name and switches to them via `saveAs:`. Never point it at an
image another VM is running.

In-place `save-clean` (and the `snapshot` command) now defer the snapshot by
0.5 s so the control reply is sent before the image is written. A snapshot taken
inside the dispatcher command replayed the command on the next launch. Wait a
moment before killing the VM after the reply.

Load after 28_sprites_stage.st."

(Smalltalk at: #AIHarness) class compile: 'cleanProject
    | app frame stage pane keep cat dialogs |
    "A clean image must not carry a hidden dialog into the snapshot."
    dialogs := Smalltalk at: #DialogBoxMorph ifAbsent: [nil].
    dialogs ifNotNil: [
        dialogs allInstances do: [:dialog |
            [dialog delete] ifError: [:e :r | nil]]].
    app := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    frame := self findFrame.
    frame ifNil: [^ ''error: no frame''].
    stage := frame workPane.
    stage ifNil: [^ ''error: no stage''].
    "A clean image must not carry old pen trails into the snapshot."
    [stage clearPenTrails] ifError: [:e :r | nil].
    keep := ''Sprite1''.
    [self dropPendingSends: ''clean''] ifError: [:e :r | nil].
    stage scripts asArray do: [:stack |
        [stack delete] ifError: [:e :r | nil]].
    stage varNames asArray do: [:variableName |
        [stage deleteVariable: variableName] ifError: [:e :r | nil]].
    stage lists keys asArray do: [:listName |
        [stage lists removeKey: listName ifAbsent: []] ifError: [:e :r | nil]].
    stage submorphs asArray do: [:morph |
        (morph isKindOf: ScratchSpriteMorph) ifTrue: [
            morph scripts asArray do: [:stack |
                [stack delete] ifError: [:e :r | nil]].
            morph varNames asArray do: [:variableName |
                [morph deleteVariable: variableName] ifError: [:e :r | nil]].
            morph lists keys asArray do: [:listName |
                [morph lists removeKey: listName ifAbsent: []]
                    ifError: [:e :r | nil]]]].
    stage sprites asArray do: [:sprite |
        (sprite objName asString = keep)
            ifFalse: [
                [stage sprites remove: sprite ifAbsent: []] ifError: [:e :r | nil].
                [sprite delete] ifError: [:e :r | nil]]].
    app ifNotNil: [app perform: #resetForProject].
    app ifNotNil: [
        cat := app perform: #targetNamed: with: keep.
        cat ifNotNil: [frame scriptsPane target: cat]].
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNotNil: [
        pane clearChat.
        [pane clearInput] ifError: [:e :r | nil].
        [pane pending: false] ifError: [:e :r | nil].
        [pane resetUsageBaseline] ifError: [:e :r | nil].
        [pane applyBridgeInfo: nil options: nil error: ''Not queried yet'']
            ifError: [:e :r | nil].
        [pane applyUsageInfo: nil error: ''Not queried yet'']
            ifError: [:e :r | nil].
        [pane selectTab: ''Chat''] ifError: [:e :r | nil].
        pane status: ''Ready''].
    Smalltalk at: #AIHarnessCanceledSends put: Set new.
    Smalltalk at: #AIHarnessCurrentSendId put: nil.
    self logLine: ''clean project: no scripts, pen trails cleared, cat only, chat cleared''.
    ^ ''ok clean''' classified: 'maintenance'.

(Smalltalk at: #AIHarness) class compile: 'saveCleanAs: newName
    | aName targetImage targetChanges dir current |
    aName := newName asString.
    (aName size > 6 and: [
        (aName copyFrom: aName size - 5 to: aName size) = ''.image''])
        ifTrue: [aName := aName copyFrom: 1 to: aName size - 6].
    aName isEmpty ifTrue: [^ ''error: empty name''].
    self cleanProject.
    targetImage := aName, ''.image''.
    targetChanges := aName, ''.changes''.
    current := Smalltalk imageName asString.
    ((current size >= targetImage size) and: [
        (current copyFrom: current size - targetImage size + 1 to: current size)
            = targetImage])
        ifTrue: [
            "Snapshot after the reply so the image never saves mid-command;
            a mid-command snapshot replays the command on the next launch."
            [(Delay forMilliseconds: 500) wait.
             Smalltalk snapshot: true andQuit: false]
                forkAt: Processor userBackgroundPriority.
            ^ ''ok save-clean '', aName].
    dir := FileDirectory default.
    [dir deleteFileNamed: targetImage] ifError: [:e :r | nil].
    [dir deleteFileNamed: targetChanges] ifError: [:e :r | nil].
    ^ self saveAs: aName' classified: 'maintenance'.

(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind sub |
    kind := req at: 1.
    kind = #load ifTrue: [
        ^ self load: (req at: 2)].
    kind = #bootstrap ifTrue: [^ self bootstrap].
    kind = #send ifTrue: [
        ^ self sendPromptText: (req at: 2)].
    kind = #''send-async'' ifTrue: [
        ^ self sendPromptTextAsync: (req at: 2)].
    kind = #poll ifTrue: [
        ^ self pollSend: (req at: 2)].
    kind = #undo ifTrue: [
        ^ self undoLast].
    kind = #clean ifTrue: [^ self cleanProject].
    kind = #''save-clean'' ifTrue: [^ self saveCleanAs: (req at: 2)].
    kind = #''release-save'' ifTrue: [^ self saveReleaseAs: (req at: 2)].
    kind = #status ifTrue: [^ self devStatus].
    kind = #log ifTrue: [^ self devLog].
    kind = #context ifTrue: [^ self devContext].
    kind = #doctor ifTrue: [^ self devDoctor].
    kind = #errors ifTrue: [^ self devErrors].
    kind = #config ifTrue: [^ self devConfigText].
    kind = #project ifTrue: [
        sub := req at: 2.
        sub = #open ifTrue: [
            self dropPendingSends: ''project open''.
            ^ self openProject: (req at: 3)].
        sub = #save ifTrue: [^ self saveProject: (req at: 3)].
        sub = #''export-text'' ifTrue: [^ self exportProjectText: (req at: 3)].
        sub = #''import-text'' ifTrue: [^ self importProjectText: (req at: 3)].
        ^ ''error: unknown project command''].
    kind = #save ifTrue: [
        self dropPendingSends: ''save''.
        ^ self saveAs: (req at: 2)].
    kind = #snapshot ifTrue: [
        self dropPendingSends: ''snapshot''.
        "Defer the snapshot until after the reply (see saveCleanAs:)."
        [(Delay forMilliseconds: 500) wait.
         Smalltalk snapshot: true andQuit: false]
            forkAt: Processor userBackgroundPriority.
        ^ ''ok snapshot''].
    ^ ''error: unknown command''' classified: 'dev server'.

(Smalltalk at: #AIHarness) logLine: 'clean-image maintenance installed'.
Transcript show: 'clean-image maintenance installed'; cr.
