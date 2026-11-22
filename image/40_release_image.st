"Release image support: end-user (fill-screen) mode with no dev tools.

A release image is a normal harness image plus a flag stored in the image:
    AIHarnessReleaseMode = true

On startup a release image:
  * does NOT start the 127.0.0.1:8767 control server or its watchdog,
  * does NOT auto-open a project or install the dev dialog policy,
  * closes non-Scratch (Squeak) windows,
  * enters Scratch's native end-user fill-screen mode (noviceMode + error
    catcher, no halos, sticky full-display frame),
  * keeps the docked Chat / Bridge / Usage rail and the async dispatcher, so
    the Chat UI and the Bridge page still work.

Build one from a clean dev image (control server on 8767 must be running):
    python tools\ai_control.py load 40_release_image.st
    python tools\ai_control.py release-save ScratchAIRelease

or:
    .\tools\make_release_image.ps1

Load last, after 36/38/37 and 39. The startUp override here intentionally
replaces the dev-mode one in 22/37."

(Smalltalk at: #AIHarness) class compile: 'releaseMode
    "True when this image was saved as an end-user build."
    (Smalltalk at: #AIHarnessReleaseMode ifAbsent: [false]) == true
        ifTrue: [^ true].
    ^ (self configAt: ''releaseMode'' ifAbsent: ''off'') asString = ''on'''
    classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'devMode
    "A release image never uses the dev dialog policy."
    self releaseMode ifTrue: [^ false].
    ^ (self configAt: ''devMode'' ifAbsent: ''off'') asString = ''on'''
    classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'closeDevWindows
    "Close Squeak tool windows without the unsaved-text prompt."
    | holderClass viewClass model dialogs |
    dialogs := Smalltalk at: #DialogBoxMorph ifAbsent: [nil].
    dialogs ifNotNil: [
        dialogs allInstances do: [:dialog |
            [dialog delete] ifError: [:e :r | nil]]].
    holderClass := Smalltalk at: #StringHolder ifAbsent: [nil].
    holderClass ifNotNil: [
        holderClass allInstances do: [:holder |
            [holder hasUnacceptedEdits: false] ifError: [:e :r | nil]]].
    "PluggableTextMorph owns the flag; the model flag is read-only."
    #(PluggableTextMorph StringHolderView) do: [:className |
        viewClass := Smalltalk at: className asSymbol ifAbsent: [nil].
        viewClass ifNotNil: [
            viewClass allInstances do: [:view |
                [view hasUnacceptedEdits: false]
                    ifError: [:e :r | nil]]]].
    World submorphs asArray do: [:m |
        (m isKindOf: SystemWindow) ifTrue: [
            model := [m model] ifError: [:e :r | nil].
            model ifNotNil: [
                [model hasUnacceptedEdits: false] ifError: [:e :r | nil]].
            [m delete] ifError: [:e :r | nil]]].
    ^ self' classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'removeReleaseDevButtons
    "The release rail has no source-reload button."
    | pane button |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ self].
    button := [pane valueOfProperty: #reloadButton] ifError: [:e :r | nil].
    button ifNotNil: [[button delete] ifError: [:e :r | nil]].
    [pane setProperty: #reloadButton toValue: nil] ifError: [:e :r | nil].
    ^ self' classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'enterReleaseMode
    "Close Squeak tool windows and use Scratch''s native end-user full screen."
    | frame |
    frame := self findFrame.
    frame ifNil: [^ self].
    self closeDevWindows.
    [ScratchFrameMorph takeOverScreen: true] ifError: [:e :r | nil].
    [frame fillScreenOn] ifError: [:e :r |
        self logDevError: ''release'' text: e asString].
    World doOneCycleNow.
    self logLine: ''release mode: fill screen, dev server off''.
    ^ self' classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'releaseWelcome
    "One short in-chat hint after a release image is cleaned."
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ self].
    [pane clearChat] ifError: [:e :r | nil].
    [pane addMessage: #assistant text:
        ''Hi! Add your API key in the Bridge tab, then ask me to build something.'']
        ifError: [:e :r | nil].
    ^ self' classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'startUp
    | dispatcher |
    self loadConfig.
    Utilities setAuthorInitials: ''ai''.
    self logLine: ''startup release='', self releaseMode printString,
        '' devMode='', self devMode printString.
    "The async send/poll and UI completion queue run on this stepping morph.
    It is not a dev tool and is required in release mode too."
    dispatcher := Smalltalk at: #AIHarnessDevDispatcher ifAbsent: [nil].
    (dispatcher isNil or: [dispatcher world isNil]) ifTrue: [
        dispatcher := (Smalltalk at: #AIHarnessDevDispatcherMorph) new.
        World addMorphFront: dispatcher.
        World startStepping: dispatcher.
        Smalltalk at: #AIHarnessDevDispatcher put: dispatcher].
    self releaseMode
        ifTrue: [
            Smalltalk at: #AIHarnessDevServerRunning put: false.
            self enterReleaseMode]
        ifFalse: [
            (self configAt: ''controlServer'' ifAbsent: ''on'') asString = ''on''
                ifTrue: [
                    self serverAlive
                        ifTrue: [
                            Smalltalk at: #AIHarnessDevServerRunning put: true]
                        ifFalse: [
                            Smalltalk at: #AIHarnessDevServerRunning put: false.
                            Smalltalk at: #AIHarnessDevHeartbeat put: 0.
                            Smalltalk at: #AIHarnessDevWatchdogRunning put: false.
                            self startDevServer.
                            self startDevWatchdog.
                            self autoOpenProject]]
                ifFalse: [
                    Smalltalk at: #AIHarnessDevServerRunning put: false.
                    Smalltalk at: #AIHarnessDevHeartbeat put: 0.
                    Smalltalk at: #AIHarnessDevWatchdogRunning put: false.
                    self autoOpenProject]].
    [self reconcileRegistry] ifError: [:e :r | nil].
    ^ self' classified: 'release'.

(Smalltalk at: #AIHarness) class compile: 'saveReleaseAs: newName
    "Clean the project, switch to end-user full screen, save a release pair."
    | aName dir targetImage targetChanges |
    aName := newName asString.
    (aName size > 6 and: [
        (aName copyFrom: aName size - 5 to: aName size) = ''.image''])
        ifTrue: [aName := aName copyFrom: 1 to: aName size - 6].
    aName isEmpty ifTrue: [^ ''error: empty name''].
    self cleanProject.
    self releaseWelcome.
    "Close windows while dev mode is still on (no modal can block the build),
    then mark the saved image as a release and remove the dev-only reload UI."
    self enterReleaseMode.
    Smalltalk at: #AIHarnessReleaseMode put: true.
    self removeReleaseDevButtons.
    dir := FileDirectory default.
    targetImage := aName, ''.image''.
    targetChanges := aName, ''.changes''.
    [dir deleteFileNamed: targetImage] ifError: [:e :r | nil].
    [dir deleteFileNamed: targetChanges] ifError: [:e :r | nil].
    dir copyFileNamed: Smalltalk changesName toFileNamed: targetChanges.
    Smalltalk logChange: ''----RELEASE '', aName, ''----'', Date dateAndTimeNow printString.
    Smalltalk imageName: (dir fullNameFor: targetImage).
    LastImageName := Smalltalk imageName.
    Smalltalk closeSourceFiles; openSourceFiles.
    "Snapshot after the reply so the control command is not replayed."
    [(Delay forMilliseconds: 500) wait.
     Smalltalk snapshot: true andQuit: false]
        forkAt: Processor userBackgroundPriority.
    ^ ''ok release '', aName' classified: 'release'.

"Hide the developer-only UI reload button and menu item in release images."
(Smalltalk at: #AIHarnessChatMorph) compile: 'ensureReloadButton
    | button |
    (Smalltalk at: #AIHarness) releaseMode ifTrue: [^ nil].
    button := self valueOfProperty: #reloadButton.
    button ifNotNil: [^ button].
    button := ScratchFrameMorph
        buttonLabel: ''Reload UI'' localized
        selector: #reloadFromButton.
    button target: self.
    button width: 72; height: 18.
    self addMorph: button.
    self setProperty: #reloadButton toValue: button.
    ^ button' classified: 'initialization'.

(Smalltalk at: #AIHarness) logLine: 'release image support installed'.
Transcript show: 'release image support installed'; cr.
