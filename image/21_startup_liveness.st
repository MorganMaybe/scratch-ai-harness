"Startup must distinguish a fresh launch from an in-place snapshot:
a fresh process has no listener on 8767 and should start the server+watchdog;
after 'snapshot' the old loop is still alive and must not be duplicated."

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
    self serverAlive
        ifTrue: [
            Smalltalk at: #AIHarnessDevServerRunning put: true]
        ifFalse: [
            Smalltalk at: #AIHarnessDevServerRunning put: false.
            Smalltalk at: #AIHarnessDevHeartbeat put: 0.
            Smalltalk at: #AIHarnessDevWatchdogRunning put: false.
            self startDevServer.
            self startDevWatchdog].
    ^ self' classified: 'dev server'.

Transcript show: 'startup liveness fix installed'; cr.
