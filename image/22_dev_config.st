"Headless dev mode: config file, error log, startup integration.

Config lives next to the image as harness.ini (key=value, # comments):
    devMode=on
    autoOpen=off
    project=C:\...\project.sb
    autoSnapshot=off
    snapshotEvery=10
    errors=C:\...\dev_errors.log

Load after 21_startup_liveness.st."

(Smalltalk at: #AIHarness) class compile: 'configPath
    | dir |
    dir := [FileDirectory dirPathFor: Smalltalk imageName] ifError: [:e :r | ''''].
    dir := dir asString.
    dir isEmpty ifTrue: [dir := self imageDir].
    (dir last = $\ or: [dir last = $/]) ifFalse: [dir := dir, ''\''].
    ^ dir, ''harness.ini''' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'loadConfig
    | text config stream line eq key value normalized path |
    config := Dictionary new.
    path := self configPath.
    text := nil.
    (FileDirectory default fileExists: path) ifTrue: [
        text := [((FileStream readOnlyFileNamed: path) contentsOfEntireFile)]
            ifError: [:e :r | nil]].
    text ifNotNil: [
        normalized := WriteStream on: String new.
        text asString do: [:ch |
            normalized nextPut: (ch = Character cr ifTrue: [Character lf] ifFalse: [ch])].
        stream := ReadStream on: normalized contents.
        [stream atEnd] whileFalse: [
            line := (stream upTo: Character lf) withBlanksTrimmed.
            (line isEmpty or: [line first = $#]) ifFalse: [
                eq := line findString: ''=''.
                eq > 0 ifTrue: [
                    key := (line copyFrom: 1 to: eq - 1) withBlanksTrimmed.
                    value := (line copyFrom: eq + 1 to: line size) withBlanksTrimmed.
                    config at: key put: value]]]].
    Smalltalk at: #AIHarnessConfig put: config.
    ^ config' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'configAt: aKey ifAbsent: aValue
    | config |
    config := Smalltalk at: #AIHarnessConfig ifAbsent: [Dictionary new].
    ^ config at: aKey ifAbsent: [aValue]' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'devMode
    ^ (self configAt: ''devMode'' ifAbsent: ''off'') asString = ''on''' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'devErrorLogPath
    ^ self configAt: ''errors'' ifAbsent: (self imageDir, ''\dev_errors.log'')' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'logDevError: kind text: aString
    | path line stream |
    path := self devErrorLogPath.
    line := Date dateAndTimeNow printString, '' ['', kind asString, ''] '', aString asString.
    stream := nil.
    (FileDirectory default fileExists: path) ifTrue: [
        stream := [FileStream fileNamed: path] ifError: [:e :r | nil]].
    stream ifNil: [stream := [FileStream newFileNamed: path] ifError: [:e :r | nil]].
    stream ifNotNil: [
        [stream setToEnd. stream nextPutAll: line; cr; close] ifError: [:e :r | nil]].
    Transcript show: ''AI dev: '', line; cr.
    ^ line' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'devConfigText
    | config out |
    config := Smalltalk at: #AIHarnessConfig ifAbsent: [Dictionary new].
    out := WriteStream on: String new.
    config keys asSortedCollection do: [:key |
        out nextPutAll: key asString, ''='', (config at: key) asString; cr].
    out nextPutAll: ''devMode='', self devMode printString; cr.
    ^ out contents' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'autoOpenProject
    | path |
    (self configAt: ''autoOpen'' ifAbsent: ''off'') asString = ''on'' ifFalse: [^ self].
    path := self configAt: ''project'' ifAbsent: ''''.
    path isEmpty ifTrue: [^ self].
    ^ [self openProject: path]
        ifError: [:e :r | self logDevError: ''autoOpen'' text: e asString. nil]' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'startUp
    | dispatcher |
    self loadConfig.
    Utilities setAuthorInitials: ''ai''.
    self logLine: ''startup devMode='', self devMode printString.
    dispatcher := Smalltalk at: #AIHarnessDevDispatcher ifAbsent: [nil].
    (dispatcher isNil or: [dispatcher world isNil]) ifTrue: [
        dispatcher := (Smalltalk at: #AIHarnessDevDispatcherMorph) new.
        World addMorphFront: dispatcher.
        World startStepping: dispatcher.
        Smalltalk at: #AIHarnessDevDispatcher put: dispatcher].
    self serverAlive
        ifTrue: [
            Smalltalk at: #AIHarnessDevServerRunning put: true]
        ifFalse: [
            Smalltalk at: #AIHarnessDevServerRunning put: false.
            Smalltalk at: #AIHarnessDevHeartbeat put: 0.
            Smalltalk at: #AIHarnessDevWatchdogRunning put: false.
            self startDevServer.
            self startDevWatchdog.
            self autoOpenProject].
    [self reconcileRegistry] ifError: [:e :r | nil].
    ^ self' classified: 'dev server'.

(Smalltalk at: #AIHarness) perform: #loadConfig.
(Smalltalk at: #AIHarness) logLine: 'dev config loaded'.
Transcript show: 'dev config installed'; cr.
