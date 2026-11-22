"Turn modal compile/syntax errors into log entries and return values.

Root cause: Compiler>>notify:at: with requestor == nil calls
SyntaxError class>>errorInClass:withCode:doitFlag:, which opens a window and
suspends the process. ClassDescription>>compile:classified: passes a
SyntaxError instance, whose notify:at:in: likewise opens a window. Either one
wedges the headless dispatcher.

Load this with the old loader (it is small and syntax-checked) before loading
anything larger."

(Smalltalk at: #Compiler) compile: 'notify: aString at: location
    requestor == nil
        ifTrue: [
            Smalltalk at: #AIHarnessLastSyntaxError put: aString asString.
            Transcript show: ''AI syntax error: '', aString asString; cr.
            ^ nil]
        ifFalse: [
            ^ requestor
                notify: aString
                at: location
                in: sourceStream]' classified: 'error handling'.

(Smalltalk at: #SyntaxError) compile: 'notify: error at: location in: source
    Smalltalk at: #AIHarnessLastSyntaxError put: error asString.
    Transcript show: ''AI compile error: '', error asString; cr.
    ^ nil' classified: 'other'.

(Smalltalk at: #SyntaxError) class compile: 'errorInClass: aClass withCode: codeString doitFlag: doit
    Smalltalk at: #AIHarnessLastSyntaxError put: ''syntax error compiling in '', aClass asString.
    Transcript show: ''AI compile error in '', aClass asString; cr.
    ^ nil' classified: 'instance creation'.

(Smalltalk at: #AIHarness) class compile: 'load: aFileName
    | path stream text result |
    path := aFileName.
    (path includes: $:) ifFalse: [
        path := (FileDirectory dirPathFor: Smalltalk imageName) asString,
            ''\..\..\image'', ''\'', aFileName].
    stream := [FileStream readOnlyFileNamed: path] ifError: [:e :r | nil].
    stream ifNil: [^ ''error: cannot open '', path].
    text := [stream contentsOfEntireFile] ifError: [:e :r | nil].
    stream close.
    text ifNil: [^ ''error: cannot read '', path].
    Smalltalk at: #AIHarnessLastSyntaxError put: nil.
    result := [Compiler evaluate: text] ifError: [:e :r | e].
    (Smalltalk at: #AIHarnessLastSyntaxError) ifNotNil: [
        ^ ''error: syntax: '', (Smalltalk at: #AIHarnessLastSyntaxError)].
    (result isKindOf: Error) ifTrue: [^ ''error: '' , result messageText asString].
    ^ ''ok load''' classified: 'dev'.

(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind |
    kind := req at: 1.
    kind = #load ifTrue: [^ self load: (req at: 2)].
    kind = #status ifTrue: [^ self devStatus].
    kind = #save ifTrue: [^ self saveAs: (req at: 2)].
    kind = #send ifTrue: [^ self sendPromptText: (req at: 2)].
    kind = #undo ifTrue: [^ self undoLast].
    ^ ''error: unknown command''' classified: 'dev server'.

Utilities setAuthorInitials: 'ai'.
Transcript show: 'safe dialogs installed'; cr.
