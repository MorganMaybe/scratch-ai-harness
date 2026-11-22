"AILiteralReader>>nextString appended an escaped quote twice, so the chat log
showed ''draw_square'' instead of 'draw_square'. Fix the unescape."

(Smalltalk at: #AILiteralReader) compile: 'nextString
    | out ch |
    out := WriteStream on: String new.
    stream next.
    [(ch := stream next) isNil] whileFalse: [
        ch = $'' ifTrue: [
            stream peek = $'' ifTrue: [
                stream next.
                out nextPut: $'']
            ifFalse: [^ out contents]]
        ifFalse: [out nextPut: ch]].
    ^ out contents' classified: 'private'.

Transcript show: 'literal reader unescape fixed'; cr.
