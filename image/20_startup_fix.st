"Fix startUp for a fresh process: the AIHarnessDevServerRunning global is saved
as true in the image, but the socket process does not survive a snapshot, so
startUp must reset the flag before starting the server. Also log each launch."

(Smalltalk at: #AIHarness) class compile: 'startUp
    | dispatcher |
    Utilities setAuthorInitials: ''ai''.
    self logLine: ''startup''.
    dispatcher := Smalltalk at: #AIHarnessDevDispatcher ifAbsent: [nil].
    (dispatcher isNil or: [dispatcher world isNil]) ifTrue: [
        dispatcher := (Smalltalk at: #AIHarnessDevDispatcherMorph) new.
        World addMorphFront: dispatcher.
        World startStepping: dispatcher.
        Smalltalk at: #AIHarnessDevDispatcher put: dispatcher].
    Smalltalk at: #AIHarnessDevServerRunning put: false.
    Smalltalk at: #AIHarnessDevHeartbeat put: 0.
    self startDevServer.
    self startDevWatchdog.
    ^ self' classified: 'dev server'.

Transcript show: 'startup fixed'; cr.
