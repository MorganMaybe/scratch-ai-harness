"Headless safety: pin author initials, log every control command, and keep the
control server alive. Load after 16a_notifier.st.

Why: Utilities class>>authorInitials loops on a 'Please type your initials:'
dialog whenever the changes file is written with blank initials, and
SystemDictionary>>openSourceFiles blanks them when the image name changes.
That modal blocks the UI thread and therefore the dispatcher, so every control
command times out. Synthetic (non-interactive) syntax errors similarly opened a
Syntax Error window before 16a_notifier.st."

(Smalltalk at: #AIHarness) class compile: 'controlLogPath
    ^ self imageDir, ''\ai_control.log''' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'logLine: aString
    | path stream |
    path := self controlLogPath.
    stream := nil.
    (FileDirectory default fileExists: path) ifTrue: [
        stream := [FileStream fileNamed: path] ifError: [:e :r | nil]].
    stream ifNil: [stream := [FileStream newFileNamed: path] ifError: [:e :r | nil]].
    stream ifNil: [^ self].
    [stream setToEnd.
     stream nextPutAll: Date dateAndTimeNow printString, '' '', aString asString;
        cr] ifError: [:e :r | nil].
    [stream close] ifError: [:e :r | nil].
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'logControl: req reply: reply
    ^ self logLine: req printString, '' -> '', reply asString' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'serverAlive
    | probe addr ok |
    Socket initializeNetwork.
    addr := NetNameResolver addressForName: ''127.0.0.1''.
    probe := Socket newTCP.
    ok := [probe connectTo: addr port: 8767.
        probe waitForConnectionUntil: (Socket deadlineSecs: 2)]
        ifError: [:e :r | false].
    [probe destroy] ifError: [:e :r | nil].
    ^ ok == true' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'ensureDevServer
    | last now |
    last := Smalltalk at: #AIHarnessDevHeartbeat ifAbsent: [0].
    now := Time millisecondClockValue.
    (now - last) < 15000 ifTrue: [^ self].
    self serverAlive
        ifTrue: [
            Smalltalk at: #AIHarnessDevHeartbeat put: now.
            ^ self].
    self logLine: ''control server is not answering; restarting''.
    Smalltalk at: #AIHarnessDevServerRunning put: false.
    self startDevServer.
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'startDevWatchdog
    (Smalltalk at: #AIHarnessDevWatchdogRunning ifAbsent: [false]) ifTrue: [^ self].
    Smalltalk at: #AIHarnessDevWatchdogRunning put: true.
    [[true] whileTrue: [
        (Delay forSeconds: 10) wait.
        [self ensureDevServer] ifError: [:e :r | nil]]]
        forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'startDevServer
    | running |
    running := Smalltalk at: #AIHarnessDevServerRunning ifAbsent: [false].
    running == true ifTrue: [^ self].
    Smalltalk at: #AIHarnessDevServerRunning put: true.
    Smalltalk at: #AIHarnessDevHeartbeat put: Time millisecondClockValue.
    Socket initializeNetwork.
    Smalltalk at: #AIHarnessDevCommands put: SharedQueue new.
    Smalltalk at: #AIHarnessDevReplies put: SharedQueue new.
    [self devServerLoop] forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'devServerLoop
    | server ms msg req reply |
    Socket initializeNetwork.
    [true] whileTrue: [
        Smalltalk at: #AIHarnessDevHeartbeat put: Time millisecondClockValue.
        server := Socket newTCP.
        [server listenOn: 8767] ifError: [
            [server destroy] ifError: [:e :r | nil].
            server := nil].
        server ifNotNil: [
            (server waitForConnectionUntil: (Socket deadlineSecs: 30)) ifTrue: [
                ms := [MessageSocket new on: server] ifError: [:e :r | nil].
                ms ifNotNil: [
                    [ms isConnected] whileTrue: [
                        Smalltalk at: #AIHarnessDevHeartbeat put: Time millisecondClockValue.
                        (([ms socket dataAvailable] ifError: [false]) and: [ms isConnected])
                            ifTrue: [
                                msg := [ms nextMessage] ifError: [:r :s | nil].
                                msg ifNotNil: [
                                    req := [(Smalltalk at: #AILiteralReader) parse: msg asString]
                                        ifError: [:e :r | nil].
                                    req ifNil: [reply := ''error: bad literal'']
                                        ifNotNil: [
                                            (Smalltalk at: #AIHarnessDevCommands) nextPut: req.
                                            reply := (Smalltalk at: #AIHarnessDevReplies) next].
                                    [ms sendMessage: reply asByteArray. ms sendData]
                                        ifError: [:e :r | nil]]].
                        (Delay forMilliseconds: 20) wait].
                    [ms destroy] ifError: [:e :r | nil]]].
            [server destroy] ifError: [:e :r | nil]].
        (Delay forSeconds: 1) wait]' classified: 'dev server'.

(Smalltalk at: #AIHarness) class compile: 'startUp
    | dispatcher |
    Utilities setAuthorInitials: ''ai''.
    dispatcher := Smalltalk at: #AIHarnessDevDispatcher ifAbsent: [nil].
    (dispatcher isNil or: [dispatcher world isNil]) ifTrue: [
        dispatcher := (Smalltalk at: #AIHarnessDevDispatcherMorph) new.
        World addMorphFront: dispatcher.
        World startStepping: dispatcher.
        Smalltalk at: #AIHarnessDevDispatcher put: dispatcher].
    self startDevServer.
    self startDevWatchdog.
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'step
    | cmds replies req reply |
    cmds := Smalltalk at: #AIHarnessDevCommands ifAbsent: [nil].
    replies := Smalltalk at: #AIHarnessDevReplies ifAbsent: [nil].
    (cmds isNil or: [replies isNil]) ifTrue: [^ self].
    [cmds isEmpty] whileFalse: [
        req := cmds next.
        reply := [(Smalltalk at: #AIHarness) perform: #handleDevCommand: with: req]
            ifError: [:err :rcvr | ''error: '', (err ifNil: [''unknown'']) asString].
        [(Smalltalk at: #AIHarness) perform: #logControl:reply: with: req with: reply]
            ifError: [:err :rcvr | nil].
        replies nextPut: reply]' classified: 'stepping'.

(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind |
    kind := req at: 1.
    kind = #load ifTrue: [
        ^ self load: (req at: 2)].
    kind = #send ifTrue: [
        ^ self sendPromptText: (req at: 2)].
    kind = #undo ifTrue: [
        ^ self undoLast].
    kind = #status ifTrue: [^ self devStatus].
    kind = #log ifTrue: [^ self devLog].
    kind = #context ifTrue: [^ self devContext].
    kind = #save ifTrue: [^ self saveAs: (req at: 2)].
    ^ ''error: unknown command''' classified: 'dev server'.

Utilities setAuthorInitials: 'ai'.
(Smalltalk at: #AIHarness) logLine: 'safe control loaded'.
