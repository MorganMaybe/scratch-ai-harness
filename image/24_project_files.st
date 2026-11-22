"Project files, doctor/errors/config commands, and optional auto-snapshot.

Load after 23_dialog_policy.st. Project paths must be absolute (the old VM's
FileDirectory helpers are unreliable)."

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
    self logLine: ''project saved '', path asString.
    ^ ''ok project save '', path asString' classified: 'project files'.

(Smalltalk at: #AIHarness) class compile: 'devDoctor
    | frame applier heartbeat age running scripts undo |
    frame := self findFrame.
    applier := Smalltalk at: #AIChangeSetApplier ifAbsent: [nil].
    heartbeat := Smalltalk at: #AIHarnessDevHeartbeat ifAbsent: [0].
    age := Time millisecondClockValue - heartbeat.
    running := Smalltalk at: #AIHarnessDevServerRunning ifAbsent: [false].
    scripts := 0.
    undo := 0.
    frame ifNotNil: [
        [frame scriptsPane target ifNotNil: [
            scripts := frame scriptsPane target scripts size]]
            ifError: [:e :r | nil].
        applier ifNotNil: [[undo := applier undoStack size] ifError: [:e :r | nil]]].
    ^ ''devMode='', self devMode printString,
        '' server='', running asString,
        '' heartbeatAge='', age printString,
        '' scripts='', scripts printString,
        '' undo='', undo printString,
        '' project='', (frame ifNil: [''none''] ifNotNil: [frame projectName asString]),
        '' syntax='', (Smalltalk at: #AIHarnessLastSyntaxError) asString,
        '' config='', self configPath,
        '' errors='', self devErrorLogPath' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'devErrors
    | path text stream |
    path := self devErrorLogPath.
    text := [((FileStream readOnlyFileNamed: path) contentsOfEntireFile) asString]
        ifError: [:e :r | nil].
    text ifNil: [^ ''(no error log at '', path, '')''].
    text size > 4000 ifTrue: [
        ^ ''...(tail)...'', (text copyFrom: text size - 3999 to: text size)].
    ^ text' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind sub |
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
    kind = #doctor ifTrue: [^ self devDoctor].
    kind = #errors ifTrue: [^ self devErrors].
    kind = #config ifTrue: [^ self devConfigText].
    kind = #project ifTrue: [
        sub := req at: 2.
        sub = #open ifTrue: [^ self openProject: (req at: 3)].
        sub = #save ifTrue: [^ self saveProject: (req at: 3)].
        ^ ''error: unknown project command''].
    kind = #save ifTrue: [^ self saveAs: (req at: 2)].
    kind = #snapshot ifTrue: [
        Smalltalk snapshot: true andQuit: false.
        ^ ''ok snapshot''].
    ^ ''error: unknown command''' classified: 'dev server'.

(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'step
    | cmds replies req reply count every |
    cmds := Smalltalk at: #AIHarnessDevCommands ifAbsent: [nil].
    replies := Smalltalk at: #AIHarnessDevReplies ifAbsent: [nil].
    (cmds isNil or: [replies isNil]) ifTrue: [^ self].
    [cmds isEmpty] whileFalse: [
        req := cmds next.
        reply := [(Smalltalk at: #AIHarness) perform: #handleDevCommand: with: req]
            ifError: [:err :rcvr | ''error: '', (err ifNil: [''unknown'']) asString].
        [(Smalltalk at: #AIHarness) perform: #logControl:reply: with: req with: reply]
            ifError: [:err :rcvr | nil].
        replies nextPut: reply.
        (((Smalltalk at: #AIHarness) configAt: ''autoSnapshot'' ifAbsent: ''off'') asString = ''on'')
            ifTrue: [
                count := (Smalltalk at: #AIHarnessDevCommandCount ifAbsent: [0]) + 1.
                Smalltalk at: #AIHarnessDevCommandCount put: count.
                every := [((Smalltalk at: #AIHarness) configAt: ''snapshotEvery'' ifAbsent: ''10'') asNumber]
                    ifError: [:e :r | 10].
                (every > 0 and: [count \\ every = 0]) ifTrue: [
                    [Smalltalk snapshot: true andQuit: false]
                        ifError: [:e :r | (Smalltalk at: #AIHarness) logDevError: ''snapshot'' text: e asString]]]]' classified: 'stepping'.

Transcript show: 'project files installed'; cr.
