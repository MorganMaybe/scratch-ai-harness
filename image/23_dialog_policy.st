"No-dialog policy, gated by devMode.

Every patched method keeps the original under a devOriginal* selector and only
logs when devMode is on. With devMode=off the image behaves exactly as before.

Load after 22_dev_config.st."

(Smalltalk at: #AIHarness) class compile: 'preserve: aSelector in: aClass as: newSelector
    ((aClass includesSelector: aSelector) and: [
        (aClass includesSelector: newSelector) not]) ifTrue: [
        aClass addSelector: newSelector withMethod: (aClass compiledMethodAt: aSelector)].
    ^ self' classified: 'dev config'.

(Smalltalk at: #AIHarness) class compile: 'preserveOriginals
    | dialog fill object popup debugger |
    dialog := (Smalltalk at: #DialogBoxMorph) class.
    fill := (Smalltalk at: #FillInTheBlank) class.
    object := Smalltalk at: #Object.
    popup := (Smalltalk at: #PopUpMenu) class.
    debugger := (Smalltalk at: #Debugger) class.
    self preserve: #inform: in: dialog as: #devOriginalInform:.
    self preserve: #inform:title: in: dialog as: #devOriginalInform:title:.
    self preserve: #inform:withDetails: in: dialog as: #devOriginalInform:withDetails:.
    self preserve: #warn: in: dialog as: #devOriginalWarn:.
    self preserve: #ask: in: dialog as: #devOriginalAsk:.
    self preserve: #askWithCancel: in: dialog as: #devOriginalAskWithCancel:.
    self preserve: #informWithCancel: in: dialog as: #devOriginalInformWithCancel:.
    self preserve: #request:initialAnswer: in: fill as: #devOriginalRequest:initialAnswer:.
    self preserve: #request: in: fill as: #devOriginalRequest:.
    self preserve: #inform: in: object as: #devOriginalInform:.
    self preserve: #inform:withDetails: in: object as: #devOriginalInform:withDetails:.
    self preserve: #confirm: in: object as: #devOriginalConfirm:.
    self preserve: #confirm:orCancel: in: object as: #devOriginalConfirm:orCancel:.
    self preserve: #inform: in: popup as: #devOriginalInform:.
    self preserve: #confirm: in: popup as: #devOriginalConfirm:.
    self preserve: #openContext:label:contents: in: debugger as: #devOriginalOpenContext:label:contents:.
    self preserve: #newFileNamed: in: (Smalltalk at: #StandardFileStream) class as: #devOriginalNewFileNamed:.
    ^ self' classified: 'dev config'.

"Save the true originals BEFORE replacing anything below."
(Smalltalk at: #AIHarness) perform: #preserveOriginals.

(Smalltalk at: #DialogBoxMorph) class compile: 'inform: informationString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''inform'' text: informationString].
    ^ self devOriginalInform: informationString' classified: 'instance creation'.

(Smalltalk at: #DialogBoxMorph) class compile: 'inform: informationString title: titleString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''inform'' text: titleString asString, '' | '', informationString asString].
    ^ self devOriginalInform: informationString title: titleString' classified: 'instance creation'.

(Smalltalk at: #DialogBoxMorph) class compile: 'inform: informationString withDetails: detailsString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''inform'' text: informationString asString, '' | '', detailsString asString].
    ^ self devOriginalInform: informationString withDetails: detailsString' classified: 'instance creation'.

(Smalltalk at: #DialogBoxMorph) class compile: 'warn: informationString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''warn'' text: informationString].
    ^ self devOriginalWarn: informationString' classified: 'instance creation'.

(Smalltalk at: #DialogBoxMorph) class compile: 'ask: questionString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''ask'' text: questionString.
            ^ false].
    ^ self devOriginalAsk: questionString' classified: 'instance creation'.

(Smalltalk at: #DialogBoxMorph) class compile: 'askWithCancel: questionString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''askWithCancel'' text: questionString.
            ^ false].
    ^ self devOriginalAskWithCancel: questionString' classified: 'instance creation'.

(Smalltalk at: #DialogBoxMorph) class compile: 'informWithCancel: informationString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''informWithCancel'' text: informationString.
            ^ true].
    ^ self devOriginalInformWithCancel: informationString' classified: 'instance creation'.

(Smalltalk at: #FillInTheBlank) class compile: 'request: aString initialAnswer: answerString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''request'' text: aString asString, '' | '', answerString asString.
            ^ answerString ifNil: ['''']].
    ^ self devOriginalRequest: aString initialAnswer: answerString' classified: 'instance creation'.

(Smalltalk at: #FillInTheBlank) class compile: 'request: aString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''request'' text: aString.
            ^ ''''].
    ^ self devOriginalRequest: aString' classified: 'instance creation'.

(Smalltalk at: #Object) compile: 'inform: aString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''inform'' text: aString].
    ^ self devOriginalInform: aString' classified: 'user interface'.

(Smalltalk at: #Object) compile: 'inform: informationString withDetails: detailsString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''inform'' text: informationString asString, '' | '', detailsString asString].
    ^ self devOriginalInform: informationString withDetails: detailsString' classified: 'user interface'.

(Smalltalk at: #Object) compile: 'confirm: queryString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''confirm'' text: queryString.
            ^ false].
    ^ self devOriginalConfirm: queryString' classified: 'error handling'.

(Smalltalk at: #Object) compile: 'confirm: aString orCancel: cancelBlock
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''confirm'' text: aString.
            ^ false].
    ^ self devOriginalConfirm: aString orCancel: cancelBlock' classified: 'error handling'.

(Smalltalk at: #PopUpMenu) class compile: 'inform: aString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [^ (Smalltalk at: #AIHarness) logDevError: ''popup-inform'' text: aString].
    ^ self devOriginalInform: aString' classified: 'general'.

(Smalltalk at: #PopUpMenu) class compile: 'confirm: aString
    (Smalltalk at: #AIHarness) devMode
        ifTrue: [
            (Smalltalk at: #AIHarness) logDevError: ''popup-confirm'' text: aString.
            ^ false].
    ^ self devOriginalConfirm: aString' classified: 'general'.

(Smalltalk at: #Debugger) class compile: 'openContext: aContext label: aString contents: contentsString
    (Smalltalk at: #AIHarness) devMode
        ifFalse: [
            ^ self devOriginalOpenContext: aContext label: aString contents: contentsString].
    (Smalltalk at: #AIHarness) logDevError: ''debugger'' text: aString asString, '' -- '', contentsString asString.
    Smalltalk at: #AIHarnessStuckProcess put: Processor activeProcess.
    Processor activeProcess suspend' classified: 'opening'.

(Smalltalk at: #StandardFileStream) class compile: 'newFileNamed: aFileName
    (Smalltalk at: #AIHarness) devMode
        ifFalse: [^ self devOriginalNewFileNamed: aFileName].
    [FileDirectory default deleteFileNamed: aFileName] ifError: [:e :r | nil].
    ^ self new open: aFileName forWrite: true' classified: 'file creation'.

Transcript show: 'dialog policy installed'; cr.
