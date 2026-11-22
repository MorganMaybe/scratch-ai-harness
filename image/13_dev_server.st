"AIHarness dev control server. One-time install:

    AIHarness load: '13_dev_server.st'.

After that, Python controls the image over 127.0.0.1:8766:

    python tools/ai_control.py status
    python tools/ai_control.py load 09_undo.st
    python tools/ai_control.py send 'draw a triangle'
    python tools/ai_control.py undo
    python tools/ai_control.py save ScratchAI5

The socket process only queues commands. A tiny stepping morph executes them
on the Morphic UI process, so the UI does not need focus and no mouse is used.
The server also starts automatically on future launches via processStartUpList.
"

(Smalltalk includesKey: #AIHarnessDevDispatcherMorph) ifFalse: [
    BorderedMorph subclass: #AIHarnessDevDispatcherMorph
        instanceVariableNames: ''
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'initialize
    super initialize.
    self extent: 1 @ 1.
    self position: 0 @ 0.
    self borderWidth: 0.
    self color: Color transparent.
    self startStepping' classified: 'initialization'.

(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'stepTime
    ^ 100' classified: 'stepping'.

(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'step
    | cmds replies req reply |
    cmds := Smalltalk at: #AIHarnessDevCommands ifAbsent: [nil].
    replies := Smalltalk at: #AIHarnessDevReplies ifAbsent: [nil].
    (cmds isNil or: [replies isNil]) ifTrue: [^ self].
    [cmds isEmpty] whileFalse: [
        req := cmds next.
        reply := [(Smalltalk at: #AIHarness) perform: #handleDevCommand: with: req]
            ifError: [:err :rcvr | ''error: '', (err ifNil: [''unknown'']) asString].
        replies nextPut: reply]' classified: 'stepping'.

(Smalltalk at: #AIHarnessChatPaneMorph) compile: 'setInputText: aString
    inputText := aString asString.
    inputMorph ifNotNil: [inputMorph setText: inputText].
    ^ true' classified: 'accessing'.

(Smalltalk at: #AIHarness) class compile: 'sendPromptText: aString
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ self].
    pane setInputText: aString.
    ^ self sendPrompt' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'startUp
    | dispatcher probe addr |
    dispatcher := Smalltalk at: #AIHarnessDevDispatcher ifAbsent: [nil].
    (dispatcher isNil or: [dispatcher world isNil]) ifTrue: [
        dispatcher := (Smalltalk at: #AIHarnessDevDispatcherMorph) new.
        World addMorphFront: dispatcher.
        World startStepping: dispatcher.
        Smalltalk at: #AIHarnessDevDispatcher put: dispatcher].
    Socket initializeNetwork.
    addr := NetNameResolver addressForName: ''127.0.0.1''.
    probe := Socket newTCP.
    probe connectTo: addr port: 8767.
    (probe waitForConnectionUntil: (Socket deadlineSecs: 1))
        ifTrue: [probe destroy. ^ self].
    probe destroy.
    Smalltalk at: #AIHarnessDevServerRunning put: false.
    self startDevServer' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'startDevServer
    | running |
    running := Smalltalk at: #AIHarnessDevServerRunning ifAbsent: [false].
    running == true ifTrue: [^ self].
    Smalltalk at: #AIHarnessDevServerRunning put: true.
    Socket initializeNetwork.
    Smalltalk at: #AIHarnessDevCommands put: SharedQueue new.
    Smalltalk at: #AIHarnessDevReplies put: SharedQueue new.
    [(Smalltalk at: #AIHarness) perform: #devServerLoop]
        forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'devServerLoop
    | server ms msg req reply |
    Socket initializeNetwork.
    [true] whileTrue: [
        server := Socket newTCP.
        [server listenOn: 8767] ifError: [
            server destroy.
            server := nil].
        server ifNotNil: [
            (server waitForConnectionUntil: (Socket deadlineSecs: 30)) ifTrue: [
                ms := MessageSocket new on: server.
                [ms isConnected] whileTrue: [
                    (([ms socket dataAvailable] ifError: [false]) and: [ms isConnected])
                        ifTrue: [
                            msg := [ms nextMessage] ifError: [nil].
                            msg ifNotNil: [
                                req := (Smalltalk at: #AILiteralReader) parse: msg asString.
                                (Smalltalk at: #AIHarnessDevCommands) nextPut: req.
                                reply := (Smalltalk at: #AIHarnessDevReplies) next.
                                ms sendMessage: reply asByteArray.
                                ms sendData]].
                    (Delay forMilliseconds: 20) wait].
                ms destroy].
            server destroy].
        (Delay forSeconds: 1) wait]' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind |
    kind := req at: 1.
    kind = #load ifTrue: [
        self load: (req at: 2).
        ^ ''ok load''].
    kind = #send ifTrue: [
        self sendPromptText: (req at: 2).
        ^ ''ok send''].
    kind = #undo ifTrue: [
        self undoLast.
        ^ ''ok undo''].
    kind = #status ifTrue: [^ self devStatus].
    kind = #save ifTrue: [^ self saveAs: (req at: 2)].
    ^ ''error: unknown command''' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'devStatus
    | applier frame sprite |
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    frame := self findFrame.
    frame ifNil: [^ ''error: no frame''].
    sprite := frame scriptsPane target.
    sprite ifNil: [^ ''error: no target''].
    ^ ''scripts='', sprite scripts size printString,
        '' registry='', (applier ifNil: [''none''] ifNotNil: [applier scripts keys asArray printString]),
        '' undo='', (applier ifNil: [0] ifNotNil: [applier undoStack size]) printString' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'saveAs: newName
    | dir newImageName newChangesName |
    dir := FileDirectory default.
    newImageName := newName, ''.image''.
    newChangesName := newName, ''.changes''.
    ((dir includesKey: newImageName) or: [dir includesKey: newChangesName])
        ifTrue: [^ ''error: name in use''].
    dir copyFileNamed: Smalltalk changesName toFileNamed: newChangesName.
    Smalltalk logChange: ''----SAVEAS '', newName, ''----'', Date dateAndTimeNow printString.
    Smalltalk imageName: (dir fullNameFor: newImageName).
    LastImageName := Smalltalk imageName.
    Smalltalk closeSourceFiles; openSourceFiles.
    Smalltalk snapshot: true andQuit: false.
    ^ ''ok save '', newName' classified: 'dev server'.

"Patch the startup list so the control server comes back after every launch."
(Smalltalk at: #SystemDictionary) compile: 'processStartUpList
    "Send #startUp to each class that needs to do something when starting up."

    #(
        DisplayScreen
        Cursor
        InputSensor
        ProcessorScheduler
        Delay
        FileDirectory
        CrLfFileStream
        ControlManager
        PasteUpMorph
        SoundBuffer
        ScratchTranslator
        AIHarness
    ) do: [:cName |
        Smalltalk at: cName ifPresent: [:cl | cl startUp]]' classified: 'snapshot and quit'.

"For a fresh image, run this once after loading the definitions:
    (Smalltalk at: #AIHarness) perform: #startUp.
Saved images start the server from processStartUpList, and reloading this file
through the control socket must not start a second server."

