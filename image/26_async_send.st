"Asynchronous chat send + poll.

Phase 1 (UI thread, #send-async): read the prompt, build the request literal
with the current project context, register a pending result, fork a worker and
return ok send <id> immediately.
Phase 2 (background process): connect to the bridge on 8765, submit the request,
wait up to 300 s and put the raw reply/error in a SharedQueue. No Morphic calls
happen here.
Phase 3 (dispatcher step, UI thread): drain the completion queue, append the
reply to the chat log, apply the change set, acknowledge with #applied and store
the reply delta for #poll.

Synchronous #send stays available as the fallback.

Load after 25_project_registry.st."

(Smalltalk at: #AIHarness) class compile: 'sendResults
    | results |
    results := Smalltalk at: #AIHarnessSendResults ifAbsent: [nil].
    results ifNil: [
        results := Dictionary new.
        Smalltalk at: #AIHarnessSendResults put: results].
    ^ results' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'sendCompletions
    | queue |
    queue := Smalltalk at: #AIHarnessSendCompletions ifAbsent: [nil].
    queue ifNil: [
        queue := SharedQueue new.
        Smalltalk at: #AIHarnessSendCompletions put: queue].
    ^ queue' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'sendGeneration
    ^ Smalltalk at: #AIHarnessSendGeneration ifAbsent: [0]' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'nextSendId
    | results id idString |
    results := self sendResults.
    id := Time millisecondClockValue.
    idString := id printString.
    [results includesKey: idString] whileTrue: [
        id := id + 1.
        idString := id printString].
    ^ idString' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'currentSendId
    ^ Smalltalk at: #AIHarnessCurrentSendId ifAbsent: [nil]' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'canceledSends
    | set |
    set := Smalltalk at: #AIHarnessCanceledSends ifAbsent: [nil].
    set ifNil: [
        set := Set new.
        Smalltalk at: #AIHarnessCanceledSends put: set].
    ^ set' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'cancelCurrentSend
    | pane id |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    id := self currentSendId.
    id ifNil: [
        pane ifNotNil: [
            pane pending: false.
            pane status: ''Nothing to cancel.''].
        ^ ''error: nothing to cancel''].
    self canceledSends add: id asString.
    pane ifNotNil: [
        pane pending: false.
        pane status: ''Cancelling...''].
    [self sendCancelFor: id] forkAt: Processor userBackgroundPriority.
    ^ ''ok cancel '', id asString' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'sendCancelFor: id
    | client addr reply |
    client := nil.
    reply := nil.
    [
        Socket initializeNetwork.
        addr := NetNameResolver addressForName: ''127.0.0.1''.
        client := MessageSocket new.
        (client connectTo: addr port: 8765 waitSecs: 2)
            ifTrue: [
                reply := [client request: (''#(#cancel '', id asString, '')'') asByteArray
                    timeoutSecs: 2] ifError: [:e :r | nil]]
    ] ifError: [:e :r | nil].
    client ifNotNil: [[client destroy] ifError: [:e :r | nil]].
    reply ifNotNil: [self logLine: ''cancel reply '', reply asString].
    ^ self' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'asyncTargetName
    | frame target |
    frame := self findFrame.
    target := ''Stage''.
    frame ifNotNil: [
        (frame scriptsPane target notNil and: [
            frame scriptsPane target isKindOf: ScratchSpriteMorph])
            ifTrue: [target := frame scriptsPane target objName]
            ifFalse: [target := ''Stage'']].
    ^ target asString' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'asyncRequestFor: prompt target: target context: context id: id
    | msg |
    msg := ''#(#request '', id asString, '' #('', (self literalString: prompt), '') '', (self literalString: target), '' ''.
    context ifNil: [msg := msg, ''nil''].
    context ifNotNil: [msg := msg, (self literalFor: context)].
    ^ msg, '')''' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'startSendAsync: aPrompt
    | pane prompt context id msg results generation paneClass |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ ''error: no chat pane''].
    prompt := aPrompt asString.
    prompt isEmpty ifTrue: [^ ''error: empty prompt''].
    paneClass := Smalltalk at: #AIHarnessChatMorph ifAbsent: [nil].
    (paneClass notNil and: [pane isKindOf: paneClass])
        ifTrue: [
            pane appendUser: prompt.
            pane pending: true.
            pane status: ''Thinking...'']
        ifFalse: [pane appendLog: ''You: '', prompt].
    pane clearInput.
    context := [self projectContext] ifError: [:e :r | nil].
    id := self nextSendId.
    Smalltalk at: #AIHarnessCurrentSendId put: id asString.
    msg := self asyncRequestFor: prompt target: self asyncTargetName
        context: context id: id.
    generation := self sendGeneration.
    results := self sendResults.
    results at: id put: (Array with: #pending with: generation).
    [(Smalltalk at: #AIHarness) perform: #runSendAsync:message:generation:
        with: id with: msg with: generation]
        forkAt: Processor userBackgroundPriority.
    self logLine: ''async send '', id, '' prompt='', prompt.
    ^ ''ok send '', id' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'sendPromptTextAsync: aString
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ ''error: no chat pane''].
    ^ self startSendAsync: aString' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'runSendAsync: id message: msgText generation: generation
    | client addr reply errorText completion |
    errorText := nil.
    reply := nil.
    client := nil.
    [
        Socket initializeNetwork.
        addr := NetNameResolver addressForName: ''127.0.0.1''.
        client := MessageSocket new.
        (client connectTo: addr port: 8765 waitSecs: 5)
            ifTrue: [
                reply := [client request: msgText asByteArray timeoutSecs: 300]
                    ifError: [:e :r | errorText := e asString. nil]]
            ifFalse: [errorText := ''bridge not reachable'']
    ] ifError: [:e :r | errorText := e asString].
    client ifNotNil: [[client destroy] ifError: [:e :r | nil]].
    reply ifNil: [errorText ifNil: [errorText := ''no bridge reply'']].
    completion := Array with: id asString with: reply with: errorText
        with: generation.
    self sendCompletions nextPut: completion.
    ^ self' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'acknowledgeAsync: id
    | client addr ack |
    ack := nil.
    client := nil.
    [
        Socket initializeNetwork.
        addr := NetNameResolver addressForName: ''127.0.0.1''.
        client := MessageSocket new.
        (client connectTo: addr port: 8765 waitSecs: 2)
            ifTrue: [
                ack := [client request: (''#(#applied '', id asString, '')'') asByteArray
                    timeoutSecs: 5] ifError: [:e :r | nil]]
    ] ifError: [:e :r | ack := nil].
    client ifNotNil: [[client destroy] ifError: [:e :r | nil]].
    ^ ack' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'applySendCompletion: anArray
    | id reply errorText generation current pane results out kind parsed ack paneClass emit showAssistant showStatus showError finish canceled prevId |
    id := (anArray at: 1) asString.
    reply := anArray at: 2.
    errorText := anArray at: 3.
    generation := anArray at: 4.
    current := self sendGeneration.
    results := self sendResults.
    prevId := self currentSendId.
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    paneClass := Smalltalk at: #AIHarnessChatMorph ifAbsent: [nil].
    out := WriteStream on: String new.
    emit := [:s | out nextPutAll: s asString; nextPut: Character lf].
    showAssistant := [:s | emit value: s.
        pane ifNotNil: [pane appendAssistant: s asString]].
    showStatus := [:s | emit value: s.
        pane ifNotNil: [pane appendStatus: s asString]].
    showError := [:s | emit value: s.
        pane ifNotNil: [pane appendError: s asString]].
    finish := [:state |
        pane ifNotNil: [
            paneClass ifNotNil: [
                (pane isKindOf: paneClass) ifTrue: [
                    pane pending: false.
                    pane status: state.
                    pane refreshCurrentPage]]]].
    canceled := self canceledSends.
    (canceled includes: id) ifTrue: [
        canceled remove: id ifAbsent: [nil].
        (prevId = id) ifTrue: [Smalltalk at: #AIHarnessCurrentSendId put: nil].
        results at: id put: (Array with: #done with: ''cancelled'').
        showStatus value: ''Cancelled.''.
        finish value: ''Ready''.
        ^ self].
    generation ~= current ifTrue: [
        (prevId = id) ifTrue: [Smalltalk at: #AIHarnessCurrentSendId put: nil].
        results at: id put: (Array with: #error with: ''error: send dropped (project changed)'') .
        finish value: ''Ready''.
        ^ self].
    errorText notNil ifTrue: [
        ((errorText asString asLowercase findString: ''cancel'') > 0)
            ifTrue: [
                (prevId = id) ifTrue: [Smalltalk at: #AIHarnessCurrentSendId put: nil].
                results at: id put: (Array with: #done with: ''cancelled'').
                showStatus value: ''Cancelled.''.
                finish value: ''Ready''.
                ^ self].
        showError value: ''Error: '', errorText asString.
        results at: id put: (Array with: #error with: ''error: '', errorText asString).
        finish value: ''Error''.
        ^ self].
    parsed := [(Smalltalk at: #AILiteralReader) parse: reply asString]
        ifError: [:e :r | nil].
    parsed ifNil: [
        showError value: ''Error: bridge reply could not be parsed''.
        results at: id put: (Array with: #error with: ''error: bad bridge reply'').
        finish value: ''Error''.
        ^ self].
    kind := parsed at: 1.
    kind = #result
        ifTrue: [
            (parsed at: 3) do: [:line | showAssistant value: line asString].
            (Smalltalk at: #AIChangeSetApplier)
                perform: #apply: with: (parsed at: 4).
            ack := self acknowledgeAsync: id.
            ack ifNotNil: [showStatus value: ''Applied. Click the green flag to try it.'']
                ifNil: [showError value: ''Error: applied, but the bridge did not acknowledge.'']]
        ifFalse: [
            kind = #error
                ifTrue: [showError value: ''Error: '', (parsed at: 3) asString]
                ifFalse: [showAssistant value: ''Bridge reply: '', reply asString]].
    (prevId = id) ifTrue: [Smalltalk at: #AIHarnessCurrentSendId put: nil].
    results at: id put: (Array with: #done with: out contents).
    finish value: (kind = #error ifTrue: [''Error''] ifFalse: [''Ready'']).
    ^ self' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'processSendCompletions
    | queue |
    queue := Smalltalk at: #AIHarnessSendCompletions ifAbsent: [nil].
    queue ifNil: [^ self].
    [queue isEmpty] whileFalse: [
        [(Smalltalk at: #AIHarness) perform: #applySendCompletion: with: queue next]
            ifError: [:e :r |
                [(Smalltalk at: #AIHarness) logDevError: ''async send'' text: e asString]
                    ifError: [:e2 :r2 | nil]]].
    ^ self' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'pollSend: idArg
    | id results entry |
    id := idArg asString.
    results := Smalltalk at: #AIHarnessSendResults ifAbsent: [nil].
    results ifNil: [^ ''error: no async sends''].
    entry := results at: id ifAbsent: [nil].
    entry ifNil: [^ ''error: unknown send '', id].
    entry first = #pending ifTrue: [^ ''pending''].
    ^ entry second' classified: 'async send'.

(Smalltalk at: #AIHarness) class compile: 'dropPendingSends: reason
    | results |
    Smalltalk at: #AIHarnessSendGeneration put: self sendGeneration + 1.
    results := Smalltalk at: #AIHarnessSendResults ifAbsent: [nil].
    results ifNil: [^ self].
    results keysDo: [:id | | entry |
        entry := results at: id.
        entry first = #pending ifTrue: [
            results at: id put: (Array with: #error with:
                (''error: send dropped ('', reason asString, '')''))]].
    ^ self' classified: 'async send'.

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
        Smalltalk snapshot: true andQuit: false.
        ^ ''ok snapshot''].
    ^ ''error: unknown command''' classified: 'dev server'.

(Smalltalk at: #AIHarnessDevDispatcherMorph) compile: 'step
    | cmds replies req reply count every |
    [(Smalltalk at: #AIHarness) perform: #processSendCompletions]
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

Smalltalk at: #AIHarnessSendResults put: Dictionary new.
Smalltalk at: #AIHarnessSendCompletions put: SharedQueue new.
Smalltalk at: #AIHarnessSendGeneration put: 0.
(Smalltalk at: #AIHarness) logLine: 'async send installed'.
Transcript show: 'async send installed'; cr.
