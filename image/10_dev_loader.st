"Dev loader. Paste this once (after 01/02 have created AIHarness), then
load any script in this folder with one short workspace line:

    AIHarness load: '09_undo.st'.

The loader reads the file and passes it to Compiler evaluate:. It uses
contentsOfEntireFile because StandardFileStream>>contents is broken in this
old image, and a backslash path because the VM rejects forward slashes.

Edit the absolute path below if the project moves."

(Smalltalk at: #AIHarness) class compile: 'load: aFileName
    | path stream text dirSep |
    dirSep := ''\''.
    path := aFileName.
    (path includes: $:) ifFalse: [
        path := (FileDirectory dirPathFor: Smalltalk imageName) asString,
            ''\..\..\image'', dirSep, aFileName].
    stream := FileStream readOnlyFileNamed: path.
    stream ifNil: [
        DialogBoxMorph inform: ''Cannot open '', path.
        ^ nil].
    text := stream contentsOfEntireFile.
    stream close.
    ^ Compiler evaluate: text' classified: 'dev'.

DialogBoxMorph inform: 'Dev loader installed. Try: AIHarness load: ''09_undo.st''.'.
