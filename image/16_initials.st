"Pin the author initials so compiling methods never opens the
'Please type your initials:' dialog (a modal that blocks the UI thread and
therefore the headless control server). Writes a small report first so the
previous state is visible in scratch/base/ai_initials.txt."

| stream |
stream := [FileStream newFileNamed: FileDirectory default pathName, '\ai_initials.txt'] ifError: [nil].
stream ifNotNil: [
    [stream nextPutAll: 'before=' , Utilities authorInitialsPerSe
        , ' image=' , Smalltalk imageName
        , ' last=' , (Smalltalk at: #LastImageName) asString; cr] ifError: [:e :r | nil].
    [stream close] ifError: [:e :r | nil]].
Utilities setAuthorInitials: 'ai'.
