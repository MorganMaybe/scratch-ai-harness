| result |
(Smalltalk includesKey: #AILiteralReader) ifFalse: [
    Object subclass: #AILiteralReader
        instanceVariableNames: 'stream'
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AILiteralReader) class compile: 'parse: aString
    ^ self new parse: aString' classified: 'parsing'.

(Smalltalk at: #AILiteralReader) compile: 'parse: aString
    stream := ReadStream on: aString.
    ^ self nextLiteral' classified: 'parsing'.

(Smalltalk at: #AILiteralReader) compile: 'nextLiteral
    | ch |
    self skipWhitespace.
    ch := stream peek.
    ch ifNil: [^ nil].
    ch = $# ifTrue: [
        stream next.
        stream peek = $( ifTrue: [^ self nextArray].
        ^ self nextSymbolName].
    ch = $( ifTrue: [^ self nextArray].
    ch = $'' ifTrue: [^ self nextString].
    (ch = $- or: [ch isDigit]) ifTrue: [^ self nextNumber].
    ^ self nextBareToken' classified: 'parsing'.

(Smalltalk at: #AILiteralReader) compile: 'skipWhitespace
    [stream peek notNil and: [stream peek isSeparator]] whileTrue: [stream next]' classified: 'private'.

(Smalltalk at: #AILiteralReader) compile: 'nextArray
    | result |
    stream next.
    result := OrderedCollection new.
    [self skipWhitespace. stream peek = $)] whileFalse: [
        stream peek ifNil: [^ result asArray].
        result add: self nextLiteral].
    stream next.
    ^ result asArray' classified: 'private'.

(Smalltalk at: #AILiteralReader) compile: 'nextSymbolName
    | out |
    out := WriteStream on: String new.
    [stream peek notNil and: [(stream peek isSeparator or: [stream peek = $)]) not]] whileTrue: [
        out nextPut: stream next].
    ^ out contents asSymbol' classified: 'private'.

(Smalltalk at: #AILiteralReader) compile: 'nextString
    | out ch |
    out := WriteStream on: String new.
    stream next.
    [(ch := stream next) isNil] whileFalse: [
        ch = $'' ifTrue: [
            stream peek = $'' ifTrue: [stream next. out nextPut: $''] ifFalse: [^ out contents]].
        out nextPut: ch].
    ^ out contents' classified: 'private'.

(Smalltalk at: #AILiteralReader) compile: 'nextNumber
    | out |
    out := WriteStream on: String new.
    stream peek = $- ifTrue: [out nextPut: stream next].
    [stream peek notNil and: [stream peek isDigit]] whileTrue: [out nextPut: stream next].
    stream peek = $. ifTrue: [
        out nextPut: stream next.
        [stream peek notNil and: [stream peek isDigit]] whileTrue: [out nextPut: stream next]].
    ^ out contents asNumber' classified: 'private'.

(Smalltalk at: #AILiteralReader) compile: 'nextBareToken
    | out token |
    out := WriteStream on: String new.
    [stream peek notNil and: [(stream peek isSeparator or: [stream peek = $)]) not]] whileTrue: [
        out nextPut: stream next].
    token := out contents.
    token = ''true'' ifTrue: [^ true].
    token = ''false'' ifTrue: [^ false].
    token = ''nil'' ifTrue: [^ nil].
    ^ token asSymbol' classified: 'private'.

result := (Smalltalk at: #AILiteralReader) parse: '#(#hello-ok ''ScratchAI/1'')'.
DialogBoxMorph inform: 'Parsed: ', result printString.
