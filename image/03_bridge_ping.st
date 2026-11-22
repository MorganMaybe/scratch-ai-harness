| client reply pane addr |
pane := Smalltalk at: #AIHarnessPane ifAbsent: [nil].
addr := NetNameResolver addressForName: '127.0.0.1'.
client := MessageSocket new.
(client connectTo: addr port: 8765 waitSecs: 5)
    ifFalse: [
        pane ifNotNil: [pane log: 'Bridge not reachable on 127.0.0.1:8765.'].
        DialogBoxMorph inform: 'Bridge not reachable on 127.0.0.1:8765. Start run_bridge.ps1 first.']
    ifTrue: [
        reply := client request: '#(#hello ''token'' ''ScratchAI/1'')' asByteArray timeoutSecs: 5.
        reply
            ifNil: [
                pane ifNotNil: [pane log: 'Bridge connected but returned no reply.'].
                DialogBoxMorph inform: 'Bridge connected but returned no reply.']
            ifNotNil: [
                pane ifNotNil: [pane log: 'Bridge replied: ', reply asString].
                DialogBoxMorph inform: 'Bridge replied: ', reply asString].
        client destroy].
