| addr ms result |
addr := NetNameResolver addressForName: '127.0.0.1'.
ms := MessageSocket new.
result := ms connectTo: addr port: 8765 waitSecs: 5.
DialogBoxMorph inform: 'MessageSocket connect=', result printString,
    ' isConnected=', ms isConnected printString,
    ' socketNil=', ms socket isNil printString.
ms destroy.
