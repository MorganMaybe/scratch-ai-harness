"Dev watcher, part 1: define the class and methods only.
Load with: AIHarness load: '11_dev_watcher.st'.
Then run: AIHarness load: '12_install_watcher.st'.

The watcher consumes trigger files in scratch/base:
  ai_load.txt  -> load the named script from image/
  ai_send.txt  -> send the file contents as a chat prompt
  ai_undo.txt  -> undo the last change set
"

(Smalltalk includesKey: #AIHarnessDevWatcherMorph) ifFalse: [
    BorderedMorph subclass: #AIHarnessDevWatcherMorph
        instanceVariableNames: ''
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessDevWatcherMorph) compile: 'initialize
    super initialize.
    self extent: 1 @ 1.
    self position: 0 @ 0.
    self borderWidth: 0.
    self color: Color transparent.
    self startStepping' classified: 'initialization'.

(Smalltalk at: #AIHarnessDevWatcherMorph) compile: 'stepTime
    ^ 1000' classified: 'stepping'.

(Smalltalk at: #AIHarnessDevWatcherMorph) compile: 'step
    | dir name |
    dir := FileDirectory default.
    (dir includesKey: ''ai_load.txt'') ifTrue: [
        name := (FileStream readOnlyFileNamed: ''ai_load.txt'') contentsOfEntireFile.
        dir deleteFileNamed: ''ai_load.txt''.
        (Smalltalk at: #AIHarness) load: name].
    (dir includesKey: ''ai_send.txt'') ifTrue: [
        name := (FileStream readOnlyFileNamed: ''ai_send.txt'') contentsOfEntireFile.
        dir deleteFileNamed: ''ai_send.txt''.
        (Smalltalk at: #AIHarness) perform: #sendPromptText: with: name].
    (dir includesKey: ''ai_undo.txt'') ifTrue: [
        dir deleteFileNamed: ''ai_undo.txt''.
        (Smalltalk at: #AIHarness) perform: #undoLast]' classified: 'stepping'.

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
