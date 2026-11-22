"Include the method header in logged syntax errors so the failing method can be
identified from the headless reply."

(Smalltalk at: #SyntaxError) compile: 'notify: error at: location in: source
    | text detail |
    text := [source contents asString] ifError: [:e :r | ''''].
    detail := error asString, '' at '', location printString.
    text size > 0 ifTrue: [
        detail := detail, '' ['', (text copyFrom: 1 to: (text size min: 90)), '']'' ].
    Smalltalk at: #AIHarnessLastSyntaxError put: detail.
    Transcript show: ''AI compile error: '', detail; cr.
    ^ nil' classified: 'other'.

(Smalltalk at: #Compiler) compile: 'notify: aString at: location
    | text detail |
    requestor == nil
        ifTrue: [
            text := [sourceStream contents asString] ifError: [:e :r | ''''].
            detail := aString asString.
            text size > 0 ifTrue: [
                detail := detail, '' ['', (text copyFrom: 1 to: (text size min: 80)), '']'' ].
            Smalltalk at: #AIHarnessLastSyntaxError put: detail.
            Transcript show: ''AI syntax error: '', detail; cr.
            ^ nil]
        ifFalse: [
            ^ requestor
                notify: aString
                at: location
                in: sourceStream]' classified: 'error handling'.

Transcript show: 'syntax detail installed'; cr.
