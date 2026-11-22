"Dev UI reload: the rail's Reload UI button and File > Reload UI set a flag.
The dev dispatcher calls processUiReloadRequest on the UI thread, which reloads
36_chat_ui_scratch.st, 38_bridge_usage_ui.st and 37_chat_dock.st, then rebuilds
the docked rail instance.

Load after 36/38/37. This file is deliberately not reloaded by the button, so the
reload logic stays stable while the UI source is being edited.

The button is a fast source reload, not a VM restart: it does not reopen the
image file. Use tools\\make_clean_image.ps1 or reopen Scratch when you need a
fresh image."

(Smalltalk at: #AIHarness) class compile: 'processUiReloadRequest
    | requested |
    requested := Smalltalk at: #AIHarnessReloadUIRequested ifAbsent: [false].
    requested == true ifFalse: [^ self].
    Smalltalk at: #AIHarnessReloadUIRequested put: false.
    ^ self reloadChatUI' classified: 'dev'.

(Smalltalk at: #AIHarness) class compile: 'reloadChatUI
    | rlNames rlFailures rlResult rlPane rlOldTab rlOldInput rlMessages |
    rlPane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    rlOldTab := nil.
    rlOldInput := ''''.
    rlMessages := OrderedCollection new.
    (rlPane notNil and: [rlPane isKindOf: AIHarnessChatMorph]) ifTrue: [
        rlOldTab := rlPane currentTab.
        rlOldInput := rlPane inputText.
        rlMessages := rlPane messages copy].
    rlNames := #(''36_chat_ui_scratch.st'' ''38_bridge_usage_ui.st'' ''37_chat_dock.st'').
    rlFailures := OrderedCollection new.
    rlNames do: [:rlName |
        rlResult := [self load: rlName] ifError: [:e :r | ''error: '', e asString].
        ((rlResult isNil) or: [rlResult asString beginsWith: ''error''])
            ifTrue: [rlFailures addLast: rlName]].
    rlFailures isEmpty ifFalse: [
        self logDevError: ''reload ui'' text: rlFailures printString.
        rlPane ifNotNil: [
            (rlPane isKindOf: AIHarnessChatMorph) ifTrue: [
                rlPane pending: false.
                rlPane status: ''Reload failed'']].
        ^ ''error: reload '', rlFailures printString].
    rlPane ifNotNil: [[rlPane delete] ifError: [:e :r | nil]].
    Smalltalk at: #AIHarnessChat put: nil.
    self ensureDockedChat.
    rlPane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    rlPane ifNotNil: [
        (rlPane isKindOf: AIHarnessChatMorph) ifTrue: [
            rlMessages do: [:entry |
                rlPane addMessage: entry role text: entry text].
            rlOldTab ifNotNil: [rlPane selectTab: rlOldTab].
            rlOldInput isEmpty ifFalse: [rlPane setInputText: rlOldInput].
            rlPane pending: false.
            rlPane status: ''UI reloaded'']].
    self logLine: ''reload ui complete''.
    ^ ''ok reload''' classified: 'dev'.

Smalltalk at: #AIHarnessReloadUIRequested put: false.
(Smalltalk at: #AIHarness) logLine: 'ui reload installed'.
Transcript show: 'ui reload installed'; cr.
