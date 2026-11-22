| init addr sock wait msg |
init := Socket initializeNetwork.
addr := NetNameResolver addressForName: '127.0.0.1'.
sock := Socket newTCP.
wait := false.
msg := 'init=', init printString, ' addr=', addr printString, ' valid=', sock isValid printString.
(addr notNil and: [sock isValid]) ifTrue: [
    sock connectTo: addr port: 8765.
    wait := sock waitForConnectionUntil: (Socket deadlineSecs: 5).
    msg := msg, ' connected=', sock isConnected printString, ' wait=', wait printString].
DialogBoxMorph inform: msg.
sock destroy.
