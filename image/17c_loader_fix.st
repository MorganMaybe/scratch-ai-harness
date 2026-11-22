"Robust dev loader.

17_safe_dialogs redefines load: with a version whose temporary `text` can fail
to compile in this image, leaving the older loader from 10_dev_loader in place.
That loader returns the last expression and can open a dialog on failure. This
version uses prefixed temporaries and always answers ok load or error: ..."

(Smalltalk at: #AIHarness) class compile: 'imageDir
    "Directory that holds the running image (normally scratch\\base)."
    | dir |
    dir := [FileDirectory dirPathFor: Smalltalk imageName] ifError: [:e :r | nil].
    dir := dir ifNil: [''''] ifNotNil: [dir asString].
    dir := dir withBlanksTrimmed.
    dir isEmpty ifTrue: [^ FileDirectory default pathName asString].
    ^ dir' classified: 'paths'.

(Smalltalk at: #AIHarness) class compile: 'repoRoot
    ^ self imageDir, ''\..\..''' classified: 'paths'.

(Smalltalk at: #AIHarness) class compile: 'imageSourceDir
    ^ self repoRoot, ''\image''' classified: 'paths'.

(Smalltalk at: #AIHarness) class compile: 'load: aFileName
    | ldPath ldStream ldSource ldResult |
    ldPath := aFileName.
    (ldPath includes: $:) ifFalse: [
        ldPath := self imageSourceDir, ''\'', aFileName].
    ldStream := [FileStream readOnlyFileNamed: ldPath] ifError: [:e :r | nil].
    ldStream ifNil: [^ ''error: cannot open '', ldPath].
    ldSource := [ldStream contentsOfEntireFile] ifError: [:e :r | nil].
    [ldStream close] ifError: [:e :r | nil].
    ldSource ifNil: [^ ''error: cannot read '', ldPath].
    Smalltalk at: #AIHarnessLastSyntaxError put: nil.
    ldResult := [Compiler evaluate: ldSource] ifError: [:e :r | e].
    (Smalltalk at: #AIHarnessLastSyntaxError) ifNotNil: [
        ^ ''error: syntax: '', (Smalltalk at: #AIHarnessLastSyntaxError)].
    (ldResult isKindOf: Error) ifTrue: [
        ^ ''error: '', ldResult messageText asString].
    ^ ''ok load''' classified: 'dev'.

Transcript show: 'robust dev loader installed'; cr.
