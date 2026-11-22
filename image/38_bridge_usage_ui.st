"Scratch-style AI chat rail - part 2: Bridge and Usage pages.

Bridge page: live #info status plus the additive #options readout (audit mode,
folder, keep, prompt budget, model options).  Usage page: model/profile,
key-presence/source and cumulative token totals from the additive #usage
message.  The key value is never requested, displayed or logged.

Both pages refresh on a background fork with a short timeout and hand results
to the UI thread through #AIHarnessChatCompletions, drained by the dev
dispatcher step (no modal dialogs, no blocking the Morphic UI).

The bridge's #info contract stays exactly nine elements; #options and #usage are
separate messages.

Load after 36_chat_ui_scratch.st.
"

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildBridgePage
    | scroll content startButton |
    bridgePage := BorderedMorph new.
    bridgePage color: Color transparent.
    bridgePage borderWidth: 0.
    self addMorph: bridgePage.

    scroll := ScrollFrameMorph2 new.
    scroll color: Color transparent.
    scroll growthFraction: 0.0.
    scroll showHorizontalScrollbar: false.
    scroll showVerticalScrollbar: true.
    bridgePage addMorph: scroll.
    bridgePage setProperty: #contentScroll toValue: scroll.

    content := Morph new.
    content color: Color transparent.
    scroll contents: content.
    bridgePage setProperty: #contentMorph toValue: content.

    refreshBridgeButton := ScratchFrameMorph
        buttonLabel: ''Refresh'' localized
        selector: #refreshBridge.
    refreshBridgeButton target: self.
    refreshBridgeButton width: 64; height: 22.
    bridgePage addMorph: refreshBridgeButton.

    startButton := ScratchFrameMorph
        buttonLabel: ''Start'' localized
        selector: #startBridge.
    startButton target: self.
    startButton width: 44; height: 22.
    bridgePage addMorph: startButton.
    bridgePage setProperty: #startBridgeButton toValue: startButton.

    pingButton := ScratchFrameMorph
        buttonLabel: ''Ping'' localized
        selector: #pingBridge.
    pingButton target: self.
    pingButton width: 40; height: 22.
    bridgePage addMorph: pingButton.

    self applyBridgeInfo: nil options: nil error: ''Not queried yet''.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildUsagePage
    | scroll content |
    usagePage := BorderedMorph new.
    usagePage color: Color transparent.
    usagePage borderWidth: 0.
    self addMorph: usagePage.

    scroll := ScrollFrameMorph2 new.
    scroll color: Color transparent.
    scroll growthFraction: 0.0.
    scroll showHorizontalScrollbar: false.
    scroll showVerticalScrollbar: true.
    usagePage addMorph: scroll.
    usagePage setProperty: #contentScroll toValue: scroll.

    content := Morph new.
    content color: Color transparent.
    scroll contents: content.
    usagePage setProperty: #contentMorph toValue: content.

    refreshUsageButton := ScratchFrameMorph
        buttonLabel: ''Refresh'' localized
        selector: #refreshUsage.
    refreshUsageButton target: self.
    refreshUsageButton width: 64; height: 22.
    usagePage addMorph: refreshUsageButton.

    self applyUsageInfo: nil error: ''Not queried yet''.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'pagePath: aString
    "Show the project-relative tail of a local diagnostic path, not the full
    user profile path."
    | s i |
    s := aString asString.
    s isEmpty ifTrue: [^ ''-''].
    i := s findString: ''scratch\base\''.
    i > 0 ifTrue: [^ s copyFrom: i to: s size].
    i := s findString: ''scratch/base/''.
    i > 0 ifTrue: [^ s copyFrom: i to: s size].
    ^ s' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'niceNumber: aValue
    | f |
    aValue ifNil: [^ ''0''].
    (aValue isKindOf: Integer) ifTrue: [^ aValue printString].
    (aValue isKindOf: Number) ifFalse: [^ aValue asString].
    f := aValue asFloat.
    (f - f truncated) abs < 0.001
        ifTrue: [^ f truncated printString]
        ifFalse: [^ f printString]' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'breakUrl: aString
    "Break a long unbroken URL/path at a slash near the value column width."
    | s i |
    s := aString asString.
    s size <= 34 ifTrue: [^ s].
    i := 34.
    [i > 1 and: [(s at: i) ~= $/]] whileTrue: [i := i - 1].
    i > 1
        ifTrue: [^ (s copyFrom: 1 to: i), String cr,
            (s copyFrom: i + 1 to: s size)].
    ^ s' classified: 'readout'.

"--- bridge page ----------------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'applyBridgeInfo: infoArray options: optionsArray error: errorText
    | rows online auditMode lastError noteText |
    rows := OrderedCollection new.
    online := infoArray notNil.
    rows addLast: (Array with: #heading with: ''Bridge'').
    rows addLast: (Array with: #section with: ''Connection'').
    online
        ifTrue: [rows addLast: (Array with: #row with: ''Status'' with: ''Online'')]
        ifFalse: [rows addLast: (Array with: #row with: ''Status'' with: ''Offline'')].
    online ifTrue: [
        rows addLast: (Array with: #row with: ''Protocol''
            with: (self field: infoArray at: 2)).
        rows addLast: (Array with: #row with: ''Profile''
            with: (self field: infoArray at: 3)).
        rows addLast: (Array with: #row with: ''Model''
            with: (self field: infoArray at: 4)).
        rows addLast: (Array with: #wide with: ''Endpoint''
            with: (self breakUrl: (self field: infoArray at: 5))).
        rows addLast: (Array with: #row with: ''Turn budget''
            with: (self niceNumber: (infoArray at: 6)), '' s'').
        Smalltalk at: #AIHarnessTurnBudget put: (infoArray at: 6).
        rows addLast: (Array with: #row with: ''Concurrent''
            with: (self textOf: (infoArray at: 7))).
        rows addLast: (Array with: #row with: ''Pending''
            with: (self textOf: (infoArray at: 8))).
        lastError := self field: infoArray at: 9.
        lastError isEmpty ifTrue: [lastError := ''(none)''  ].
        rows addLast: (Array with: #row with: ''Last error'' with: lastError)].
    online ifFalse: [
        rows addLast: (Array with: #row with: ''Last error''
            with: (errorText ifNil: [''not reachable'']))].
    rows addLast: (Array with: #gap with: 6).
    rows addLast: (Array with: #section with: ''Options'').
    optionsArray ifNil: [
        rows addLast: (Array with: #row with: ''Auditing'' with: ''unavailable'')]
    ifNotNil: [
        auditMode := self field: optionsArray at: 2.
        rows addLast: (Array with: #row with: ''Auditing'' with: auditMode).
        auditMode = ''full''
            ifTrue: [noteText := ''Local only: prompts and raw replies. Do not share.'']
            ifFalse: [
                auditMode = ''meta''
                    ifTrue: [noteText := ''Local index only.'']
                    ifFalse: [noteText := ''Audit capture is off.'']].
        rows addLast: (Array with: #note with: noteText).
        rows addLast: (Array with: #row with: ''Audit folder''
            with: (self pagePath: (self field: optionsArray at: 3))).
        rows addLast: (Array with: #row with: ''Audit keep''
            with: (self textOf: (optionsArray at: 4)), '' turns'').
        rows addLast: (Array with: #row with: ''Prompt budget''
            with: (self textOf: (optionsArray at: 5)), '' chars'').
        rows addLast: (Array with: #row with: ''Timeout''
            with: (self niceNumber: (optionsArray at: 6)), '' s'').
        rows addLast: (Array with: #row with: ''Retries''
            with: (self textOf: (optionsArray at: 7))).
        rows addLast: (Array with: #row with: ''Max tokens''
            with: (self textOf: (optionsArray at: 8))).
        rows addLast: (Array with: #row with: ''Thinking''
            with: (self field: optionsArray at: 9)).
        rows addLast: (Array with: #row with: ''Log file''
            with: (self pagePath: (self field: optionsArray at: 10)))].
    self setPageRows: bridgePage fields: bridgeFields rows: rows.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'bridgeStatusField
    | row |
    row := self bridgeFields detect: [:r |
        (r isKindOf: Array) and: [
            (r at: 1) = #row and: [
                (r at: 2) contents asString = ''Status:'']]] ifNone: [nil].
    row ifNil: [^ nil].
    ^ row at: 3' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'updateBridgeStatus: aString
    | field |
    field := self bridgeStatusField.
    field ifNil: [^ self].
    field contents: aString asString.
    field fitContents.
    self layoutFields: bridgeFields page: bridgePage.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'refreshBridge
    | pane |
    pane := self.
    self updateBridgeStatus: ''Refreshing...''.
    [pane fetchBridgeInfo] forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'fetchBridgeInfo
    | info options errorText |
    errorText := nil.
    info := self requestBridgeLiteral: ''#(#info)''.
    info ifNil: [errorText := ''bridge not reachable on 127.0.0.1:8765''].
    info ifNotNil: [
        options := self requestBridgeLiteral: ''#(#options)''].
    (Smalltalk at: #AIHarness) chatUiCompletions
        nextPut: (Array with: #bridge with: info with: options with: errorText).
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'pingBridge
    | pane |
    pane := self.
    [pane fetchPing] forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'fetchPing
    | reply |
    reply := self requestBridgeLiteral: ''#(#ping)''.
    (Smalltalk at: #AIHarness) chatUiCompletions
        nextPut: (Array with: #ping with: reply).
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'applyPingResult: aReply
    | text |
    aReply ifNil: [
        text := ''Offline (no reply)'']
    ifNotNil: [
        (aReply at: 1) = #pong
            ifTrue: [text := ''Online (pong)'']
            ifFalse: [text := ''Online ('', (self shorten: aReply printString), '')'']].
    self status: ''Bridge: '', text.
    self updateBridgeStatus: text.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'startBridgeButton
    "Read through the page property so a live UI reload needs no class-shape
    change (the 36 class definition only runs on first creation)."
    bridgePage ifNil: [^ nil].
    ^ bridgePage valueOfProperty: #startBridgeButton' classified: 'bridge page'.

"--- starting the bridge from the page -------------------------------------
The image VM has no process-spawn primitive, so the Start button writes a tiny
.cmd launcher next to the image and hands it to Windows through the Scratch
shell hook (ScratchPlugin primOpenURL:).  The launcher runs run_live.ps1 when a
key file is present (or bridgeLaunch=live) and the mock bridge otherwise.  The
work is forked; the page polls #info and refreshes through the completion
queue, so the UI never blocks."
(Smalltalk at: #AIHarnessChatMorph) compile: 'startBridge
    | pane |
    pane := self.
    self updateBridgeStatus: ''Starting...''.
    [[pane launchBridge] ifError: [:e :r |
        (Smalltalk at: #AIHarness) chatUiCompletions
            nextPut: (Array with: #bridgeLaunch
                with: ''Start failed: '', e asString)]]
        forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'launchBridge
    | mode text info options |
    info := [self requestBridgeLiteral: ''#(#info)''] ifError: [:e :r | nil].
    info isNil ifTrue: [
        mode := [self bridgeLaunchMode] ifError: [:e :r | ''mock''].
        text := [self runBridgeLauncher: mode]
            ifError: [:e :r | ''Start failed: '', e asString].
        (Smalltalk at: #AIHarness) chatUiCompletions
            nextPut: (Array with: #bridgeLaunch with: text).
        (text beginsWith: ''Starting'') ifFalse: [^ self].
        (self waitForBridgeReply: 40)
            ifTrue: [
                info := [self requestBridgeLiteral: ''#(#info)'']
                    ifError: [:e :r | nil]]
            ifFalse: [
                (Smalltalk at: #AIHarness) chatUiCompletions
                    nextPut: (Array with: #bridgeLaunch
                        with: ''Start timed out (no #info on 8765)'')]].
    info ifNotNil: [
        options := [self requestBridgeLiteral: ''#(#options)''] ifError: [:e :r | nil].
        (Smalltalk at: #AIHarness) chatUiCompletions
            nextPut: (Array with: #bridge with: info with: options with: nil)].
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'waitForBridgeReply: aCount
    "Answer true if #info answers within aCount attempts (500 ms apart)."
    | i |
    i := 0.
    [i < aCount] whileTrue: [
        (self requestBridgeLiteral: ''#(#info)'') ifNotNil: [^ true].
        i := i + 1.
        (Delay forMilliseconds: 500) wait].
    ^ false' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'applyBridgeLaunchStatus: aText
    self updateBridgeStatus: aText asString.
    ^ self' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'bridgeRepoRoot
    "The image runs with scratch\base as its working directory."
    ^ FileDirectory default pathName, ''\..\..''' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'fileExists: aPath
    "Never use readOnlyFileNamed: here: a missing path opens a file chooser."
    ^ [FileDirectory default fileExists: aPath]
        ifError: [:e :r | false]' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'bridgeLaunchMode
    "live | mock.  harness.ini bridgeLaunch wins; auto follows the key file."
    | configured |
    configured := [((Smalltalk at: #AIHarness)
        configAt: ''bridgeLaunch'' ifAbsent: ''auto'') asString]
        ifError: [:e :r | ''auto''].
    configured := configured withBlanksTrimmed asLowercase.
    configured = ''live'' ifTrue: [^ ''live''].
    configured = ''mock'' ifTrue: [^ ''mock''].
    (self fileExists: self bridgeRepoRoot, ''\bridge\.deepseek_key'')
        ifTrue: [^ ''live''].
    ^ ''mock''' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'runBridgeLauncher: aMode
    | path text |
    path := FileDirectory default pathName, ''\bridge_start.cmd''.
    text := self writeBridgeLauncher: aMode at: path.
    text = ''ok'' ifFalse: [^ text].
    [ScratchPlugin primOpenURL: path] ifError: [:e :r | ^ ''Start failed: '', e asString].
    ^ ''Starting ('', aMode, '')''' classified: 'bridge page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'writeBridgeLauncher: aMode at: aPath
    | script stream runScript nl |
    nl := String crlf.
    script := WriteStream on: String new.
    script nextPutAll: ''@echo off'', nl.
    script nextPutAll: ''title Scratch AI bridge ('', aMode, '')'', nl.
    aMode = ''live''
        ifTrue: [runScript := ''run_live.ps1'']
        ifFalse: [runScript := ''run_bridge.ps1''].
    script nextPutAll: ''powershell -NoProfile -ExecutionPolicy Bypass -File "''
        , self bridgeRepoRoot , ''\'', runScript , ''"'', nl.
    script nextPutAll: ''if errorlevel 1 pause'', nl.
    stream := [FileStream newFileNamed: aPath] ifError: [:e :r | nil].
    stream ifNil: [^ ''Start failed: cannot write '', aPath].
    [stream nextPutAll: script contents] ifError: [:e :r |
        [stream close] ifError: [:e2 :r2 | nil].
        ^ ''Start failed: '', e asString].
    [stream close] ifError: [:e :r | nil].
    ^ ''ok''' classified: 'bridge page'.

"--- usage page -----------------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'applyUsageInfo: usageArray error: errorText
    | rows model profile keyEnv keyPresent prompt completion total requests previous prevRequests lastTurn budget lastText |
    rows := OrderedCollection new.
    rows addLast: (Array with: #heading with: ''Usage'').
    rows addLast: (Array with: #section with: ''Connection'').
    usageArray ifNil: [
        rows addLast: (Array with: #row with: ''Status'' with: ''Offline'').
        rows addLast: (Array with: #row with: ''Last error''
            with: (errorText ifNil: [''usage unavailable'']))]
    ifNotNil: [
        rows addLast: (Array with: #row with: ''Status'' with: ''Online'').
        model := self field: usageArray at: 6.
        profile := self field: usageArray at: 7.
        keyEnv := self field: usageArray at: 8.
        keyPresent := false.
        usageArray size >= 9 ifTrue: [keyPresent := (usageArray at: 9) == true].
        prompt := usageArray at: 2.
        completion := usageArray at: 3.
        total := usageArray at: 4.
        requests := usageArray at: 5.
        model isEmpty ifTrue: [model := ''-''].
        profile isEmpty ifTrue: [profile := ''-''].
        rows addLast: (Array with: #row with: ''Model'' with: model).
        rows addLast: (self modelSwitcherRowFor: model).
        rows addLast: (Array with: #note
            with: ''The * marks the active model. A switch applies to the next turn and resets when the bridge restarts.'').
        rows addLast: (Array with: #row with: ''Profile'' with: profile).
        keyEnv isEmpty
            ifTrue: [rows addLast: (Array with: #row with: ''Key''
                with: ''not used by this profile'')]
            ifFalse: [
                keyPresent
                    ifTrue: [rows addLast: (Array with: #row with: ''Key''
                        with: keyEnv, '' (configured)'')]
                    ifFalse: [rows addLast: (Array with: #row with: ''Key''
                        with: keyEnv, '' (missing)'')]].
        rows addLast: (Array with: #row with: ''Key source''
            with: ''environment variable'').
        rows addLast: (Array with: #note
            with: ''The key value is never displayed.'').
        rows addLast: (Array with: #gap with: 6).
        rows addLast: (Array with: #section with: ''Since bridge start'').
        rows addLast: (Array with: #row with: ''Prompt tokens''
            with: (self formatCount: prompt)).
        rows addLast: (Array with: #row with: ''Completion tokens''
            with: (self formatCount: completion)).
        rows addLast: (Array with: #row with: ''Total tokens''
            with: (self formatCount: total)).
        rows addLast: (Array with: #row with: ''Requests''
            with: (self formatCount: requests)).

        previous := lastUsageTotal.
        prevRequests := Smalltalk at: #AIHarnessUsageRequests ifAbsent: [nil].
        lastTurn := Smalltalk at: #AIHarnessLastTurnTokens ifAbsent: [nil].
        ((previous notNil and: [total < previous]) or: [
            prevRequests notNil and: [requests < prevRequests]])
                ifTrue: [
                    lastTurn := nil.
                    Smalltalk at: #AIHarnessLastTurnTokens put: nil.
                    prevRequests := nil].
        (previous notNil and: [
            prevRequests notNil and: [requests > prevRequests]])
                ifTrue: [
                    lastTurn := total - previous.
                    Smalltalk at: #AIHarnessLastTurnTokens put: lastTurn].
        lastUsageTotal := total.
        Smalltalk at: #AIHarnessUsageRequests put: requests.
        lastText := ''-''.
        lastTurn ifNotNil: [
            lastText := (self formatCount: lastTurn), '' tokens''].
        rows addLast: (Array with: #row with: ''Last turn'' with: lastText).
        budget := Smalltalk at: #AIHarnessTurnBudget ifAbsent: [nil].
        rows addLast: (Array with: #row with: ''Turn budget''
            with: (budget ifNil: [''-''] ifNotNil: [(self niceNumber: budget), '' s''])).
        rows addLast: (Array with: #note
            with: ''Totals reset when the bridge restarts.'')].
    self setPageRows: usagePage fields: usageFields rows: rows.
    ^ self' classified: 'usage page'.

"--- model switcher -------------------------------------------------------
The two buttons mirror bridge/config.py MODEL_CHOICES (1-based order).  A
switch is a short-lived request on a background fork; the completion queue
re-applies the Usage page on the UI thread, so no Morphic call blocks."
(Smalltalk at: #AIHarnessChatMorph) compile: 'modelButtonLabel: aLabel model: aModel active: activeModel
    ^ aModel = activeModel
        ifTrue: [aLabel, '' *'']
        ifFalse: [aLabel]' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'modelSwitcherRowFor: activeModel
    | row deepSeek hy4 |
    row := Morph new.
    row color: Color transparent.
    deepSeek := ScratchFrameMorph
        buttonLabel: (self modelButtonLabel: ''DeepSeek''
            model: ''deepseek-v4.1-flash'' active: activeModel)
        selector: #useDeepSeekModel.
    deepSeek target: self.
    deepSeek width: 86; height: 22.
    deepSeek position: 0 @ 0.
    row addMorph: deepSeek.
    hy4 := ScratchFrameMorph
        buttonLabel: (self modelButtonLabel: ''HY4 Flash Free''
            model: ''hy4-flash-free'' active: activeModel)
        selector: #useHy4Model.
    hy4 target: self.
    hy4 width: 124; height: 22.
    hy4 position: (deepSeek right + 6) @ 0.
    row addMorph: hy4.
    row extent: hy4 right @ 22.
    ^ row' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'useDeepSeekModel
    self selectModelAt: 1.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'useHy4Model
    self selectModelAt: 2.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'selectModelAt: anIndex
    | pane |
    pane := self.
    self updateUsageStatus: ''Switching model...''.
    [pane requestModelSelection: anIndex]
        forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'requestModelSelection: anIndex
    | reply |
    reply := self requestBridgeLiteral: ''#(#selectModel '', anIndex printString, '')''.
    (Smalltalk at: #AIHarness) chatUiCompletions
        nextPut: (Array with: #modelSwitch with: reply).
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'applyModelSwitch: aReply
    | name |
    aReply ifNil: [
        self updateUsageStatus: ''Switch failed: bridge not reachable''.
        ^ self].
    (aReply isKindOf: Array) ifFalse: [
        self updateUsageStatus: ''Switch failed: unexpected reply''.
        ^ self].
    (aReply at: 1) = #model
        ifTrue: [
            name := self field: aReply at: 2.
            self status: ''Model: '', name.
            self refreshUsage]
        ifFalse: [
            name := (aReply at: 1) = #error
                ifTrue: [self field: aReply at: 3]
                ifFalse: [self field: aReply at: 2].
            name isEmpty ifTrue: [name := ''unknown error''].
            self updateUsageStatus: ''Switch failed: '', name].
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'usageStatusField
    | row |
    row := self usageFields detect: [:r |
        (r isKindOf: Array) and: [
            (r at: 1) = #row and: [
                (r at: 2) contents asString = ''Status:'']]] ifNone: [nil].
    row ifNil: [^ nil].
    ^ row at: 3' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'updateUsageStatus: aString
    | field |
    field := self usageStatusField.
    field ifNil: [^ self].
    field contents: aString asString.
    field fitContents.
    self layoutFields: usageFields page: usagePage.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'resetUsageBaseline
    lastUsageTotal := nil.
    Smalltalk at: #AIHarnessUsageRequests put: nil.
    Smalltalk at: #AIHarnessLastTurnTokens put: nil.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'refreshUsage
    | pane |
    pane := self.
    self updateUsageStatus: ''Refreshing...''.
    [pane fetchUsage] forkAt: Processor userBackgroundPriority.
    ^ self' classified: 'usage page'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'fetchUsage
    | usage |
    usage := self requestBridgeLiteral: ''#(#usage)''.
    (Smalltalk at: #AIHarness) chatUiCompletions
        nextPut: (Array with: #usage with: usage with: nil).
    ^ self' classified: 'usage page'.

"--- one short-lived bridge request --------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'requestBridgeLiteral: aString
    | client addr reply parsed |
    parsed := nil.
    client := nil.
    [Socket initializeNetwork.
     addr := NetNameResolver addressForName: ''127.0.0.1''.
     client := MessageSocket new.
     (client connectTo: addr port: 8765 waitSecs: 2)
        ifTrue: [
            reply := [client request: aString asByteArray timeoutSecs: 2]
                ifError: [:e :r | nil].
            reply ifNotNil: [
                parsed := [(Smalltalk at: #AILiteralReader) parse: reply asString]
                    ifError: [:e :r | nil]]]
        ifFalse: [parsed := nil]]
        ifError: [:e :r | parsed := nil].
    client ifNotNil: [[client destroy] ifError: [:e :r | nil]].
    ^ parsed' classified: 'bridge request'.

"--- class-side wrappers --------------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'refreshBridgeInfo
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (pane notNil and: [pane isKindOf: AIHarnessChatMorph]) ifTrue: [pane refreshBridge].
    ^ self' classified: 'chat ui'.

(Smalltalk at: #AIHarness) class compile: 'refreshUsageInfo
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (pane notNil and: [pane isKindOf: AIHarnessChatMorph]) ifTrue: [pane refreshUsage].
    ^ self' classified: 'chat ui'.

"--- dispatcher: drain Bridge/Usage completions on the UI thread ----------
The body matches 26_async_send.st plus one extra queue drain."
(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'step
    | cmds replies req reply count every |
    [(Smalltalk at: #AIHarness) perform: #processSendCompletions]
        ifError: [:e :r | nil].
    [(Smalltalk at: #AIHarness) perform: #processChatUiCompletions]
        ifError: [:e :r | nil].
    [(Smalltalk at: #AIHarness) perform: #processUiReloadRequest]
        ifError: [:e :r | nil].
    [(Smalltalk at: #AIHarness) perform: #ensureChatDocked]
        ifError: [:e :r | nil].
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

"Rebuild the live pages with the structured rows and scrollers."
[
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (pane notNil and: [
        (pane isKindOf: AIHarnessChatMorph) and: [
            (pane valueOfProperty: #layoutVersion) = 13]]) ifTrue: [
        pane refreshBridge.
        pane refreshUsage]] value.

(Smalltalk at: #AIHarness) logLine: 'chat bridge/usage pages installed'.
Transcript show: 'chat bridge/usage pages installed'; cr.
