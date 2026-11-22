"Dev watcher, part 2: install the watcher morph.
Load with: AIHarness load: '12_install_watcher.st'.
Run this after 11_dev_watcher.st."

| watcher |
watcher := Smalltalk at: #AIHarnessDevWatcher ifAbsent: [nil].
(watcher isNil or: [watcher world isNil]) ifTrue: [
    watcher := (Smalltalk at: #AIHarnessDevWatcherMorph) new.
    World addMorphFront: watcher.
    World startStepping: watcher.
    watcher startStepping.
    Smalltalk at: #AIHarnessDevWatcher put: watcher].
DialogBoxMorph inform: 'Dev watcher active. Drop ai_load.txt, ai_send.txt, or ai_undo.txt in scratch/base.'.
