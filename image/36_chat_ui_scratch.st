"Scratch-style AI chat rail - part 1: classes, Chat page, message model.

This replaces the floating dark BorderedMorph chat with a docked pane that
copies Scratch's own visuals:

  * DividedImageFrameMorph with #blocksPaletteFrameTransparent2 and the
    ScratchFrameMorph palette grey (same surface as the left blocks palette);
  * ScratchTabPaneMorph with #tabOn/#tabOff for Chat / Bridge / Usage;
  * assistant text: white MultilineStringMorph on the grey rail;
  * user messages: white ScratchTalkBubbleMorph bubbles, dark text;
  * input: the #typein name-field skin with a white-on-grey multiline editor;
  * buttons: ScratchFrameMorph buttonLabel:selector: (#btn/#btnPressed).

The old AIHarnessChatPaneMorph stays compiled but inert.  The global
#AIHarnessChat points at the new AIHarnessChatMorph instance, and the new class
implements the same selectors (inputText, acceptInput, clearInput, appendLog:,
clearChat, logText, setInputText:) so the control server and the async send path
keep working unchanged.

This image's ifNil:ifNotNil: blocks take zero arguments.  Never write
ifNotNil: [:x | ...] here.

Load order: 36_chat_ui_scratch.st -> 38_bridge_usage_ui.st -> 37_chat_dock.st.
"

"--- message model -------------------------------------------------------"
(Smalltalk includesKey: #AIHarnessChatMessage) ifFalse: [
    Object subclass: #AIHarnessChatMessage
        instanceVariableNames: 'role text time morph'
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessChatMessage) class compile: 'role: aSymbol text: aString
    ^ self new setRole: aSymbol text: aString' classified: 'instance creation'.

(Smalltalk at: #AIHarnessChatMessage) compile: 'setRole: aSymbol text: aString
    role := aSymbol.
    text := aString asString.
    time := Time millisecondClockValue.
    ^ self' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatMessage) compile: 'role
    ^ role' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatMessage) compile: 'text
    ^ text ifNil: ['''']' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatMessage) compile: 'time
    ^ time' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatMessage) compile: 'morph
    ^ morph' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatMessage) compile: 'morph: aMorph
    morph := aMorph.
    ^ self' classified: 'accessing'.

"--- user bubble: a white talk-bubble card with dark text ------------------"
(Smalltalk includesKey: #AIHarnessChatBubbleMorph) ifFalse: [
    ScratchTalkBubbleMorph subclass: #AIHarnessChatBubbleMorph
        instanceVariableNames: ''
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessChatBubbleMorph) compile: 'initialize
    super initialize.
    self noPointer.
    ^ self' classified: 'initialization'.

"ScratchTalkBubbleMorph reserves a pointer strip; a chat card does not need it.
ImageFrameMorph answers self bottom, which is the normal value."
(Smalltalk at: #AIHarnessChatBubbleMorph) compile: 'insetBottom
    ^ self bottom' classified: 'geometry'.

(Smalltalk at: #AIHarnessChatBubbleMorph) compile: 'setMessage: aString maxWidth: aNumber
    | text maxWidth |
    maxWidth := aNumber max: 80.
    self initFromForm: (ScratchFrameMorph skinAt: #talkBubbleFrame).
    self noPointer.
    text := aString asString withBlanksTrimmed.
    contentsMorph ifNotNil: [
        contentsMorph centerText: false.
        contentsMorph textColor: Color black.
        contentsMorph width: maxWidth.
        contentsMorph contents: text.
        contentsMorph fitContents.
        self extent: (contentsMorph extent + (14@10)).
        contentsMorph position: self position + (7@5)].
    ^ self' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatBubbleMorph) compile: 'alignContents
    contentsMorph ifNotNil: [contentsMorph position: self position + (7@5)].
    ^ self' classified: 'geometry'.

"--- history: a vertical stack of message morphs --------------------------"
(Smalltalk includesKey: #AIHarnessChatHistoryMorph) ifFalse: [
    BorderedMorph subclass: #AIHarnessChatHistoryMorph
        instanceVariableNames: ''
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessChatHistoryMorph) compile: 'initialize
    super initialize.
    self color: Color transparent.
    self borderWidth: 0.
    self extent: 300 @ 120.
    ^ self' classified: 'initialization'.

"Stack messages top to bottom.  Positions in this image are absolute, so every
child is placed relative to my own bounds.  The right 20 px is reserved for the
scratch scrollbar, so bubbles stop short of it while status lines stay centred
on the visible page."
(Smalltalk at: #AIHarnessChatHistoryMorph) compile: 'fixLayout
    | y w m |
    w := self width max: 80.
    y := 4.
    "submorphs are front-first: reverse them so the oldest message is on top"
    self submorphs reverseDo: [:each |
        m := each.
        (m isKindOf: (Smalltalk at: #AIHarnessChatBubbleMorph))
            ifTrue: [
                m position: ((self left + w - 20 - m width) @ (self top + y)).
                m alignContents]
            ifFalse: [
                (m isKindOf: MultilineStringMorph)
                    ifTrue: [
                        m width: (w - 44).
                        m contents: m contents.
                        m fitContents.
                        m position: (self left + 14) @ (self top + y)]
                    ifFalse: [
                        m position: (self left + ((w - m width) // 2)) @ (self top + y)]].
        y := y + m height + 7].
    self extent: w @ (y + 4).
    ^ self' classified: 'layout'.

"--- multiline input: Scratch name-field look, white text -----------------"
(Smalltalk includesKey: #AIHarnessChatInputMorph) ifFalse: [
    MultilineStringMorph subclass: #AIHarnessChatInputMorph
        instanceVariableNames: ''
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessChatInputMorph) compile: 'initialize
    super initialize.
    self isEditable: true.
    self textColor: Color white.
    self color: Color transparent.
    self font: (ScratchFrameMorph getFont: #UpdatingStringField).
    self growWithText: true.
    self contents: ''''.
    self extent: 280 @ 18.
    ^ self' classified: 'initialization'.

"Enter sends; Shift+Enter inserts a newline.  Every other key uses the normal
MultilineStringMorph editing path (including the Alt+V paste trap workaround)."
(Smalltalk at: #AIHarnessChatInputMorph) compile: 'keyStroke: evt
    | ch pane |
    ch := evt unicodeChar.
    ch = 0 ifTrue: [ch := evt keyValue].
    ((ch = 13) or: [ch = 10]) ifTrue: [
        evt shiftPressed
            ifTrue: [
                self insertString: (UTF32 with: 13).
                ^ self]
            ifFalse: [
                pane := self ownerThatIsA: (Smalltalk at: #AIHarnessChatMorph).
                pane ifNotNil: [pane sendFromChat].
                ^ self]].
    ^ super keyStroke: evt' classified: 'events'.

(Smalltalk at: #AIHarnessChatInputMorph) compile: 'contents: aString
    | pane |
    super contents: aString.
    self height: (self height max: 18).
    pane := self ownerThatIsA: (Smalltalk at: #AIHarnessChatMorph).
    pane ifNotNil: [
        pane updatePlaceholder.
        pane fixLayout].
    ^ self' classified: 'accessing'.

"Typing goes through MultilineStringMorph>>insertString: -> lineWrapFrom:, not
contents:.  Notify the rail so the placeholder disappears and the input frame
grows/shifts with the editor."
(Smalltalk at: #AIHarnessChatInputMorph) compile: 'lineWrapFrom: startLine
    super lineWrapFrom: startLine.
    self notifyPane.
    ^ self' classified: 'accessing'.

(Smalltalk at: #AIHarnessChatInputMorph) compile: 'notifyPane
    | pane |
    pane := self ownerThatIsA: (Smalltalk at: #AIHarnessChatMorph).
    pane ifNotNil: [pane inputChanged].
    ^ self' classified: 'accessing'.

"--- the docked pane ------------------------------------------------------"
(Smalltalk includesKey: #AIHarnessChatMorph) ifFalse: [
    DividedImageFrameMorph subclass: #AIHarnessChatMorph
        instanceVariableNames: 'tabPane currentTab chatPage bridgePage usagePage historyPane historyMorph inputFrame inputScroller inputMorph inputText placeholderMorph clearButton undoButton sendButton refreshBridgeButton pingButton refreshUsageButton statusMorph bridgeFields usageFields collapseButton messages collapsed pending lastUsageTotal'
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk at: #AIHarnessChatMorph) class compile: 'dockWidth
    "352 px native reservation.  The visual rail adds railOverlap on the left so
    its Scripts left edge covers the outer library right edge."
    ^ 352' classified: 'constants'.

(Smalltalk at: #AIHarnessChatMorph) class compile: 'railOverlap
    "The rail starts this many px left of the native reservation so the Scripts
    left edge and bottom-left corner overlap the native library right edge."
    ^ 6' classified: 'constants'.

(Smalltalk at: #AIHarnessChatMorph) class compile: 'minDockFrameWidth
    ^ 1260' classified: 'constants'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'initialize
    | src lib frameForm bg header topLeft topRight bottomLeft bottomRight rightEdge topEdge bottomEdge bottomCol leftEdge curve corner libCorner |
    super initialize.
    "Left side: native Scripts pane corner/edge, so the rail gets a real rounded
    bottom-left corner.  Right side and bottom edge: native library forms, so the
    outer right and bottom still match the native window.  The native library
    right edge remains the seam on the left."
    src := ScratchFrameMorph skinAt: #scriptPaneFrameTransparent2.
    lib := ScratchFrameMorph skinAt: #spriteLibraryPaneFrameTransparent2.
    frameForm := Form extent: 34 @ 56 depth: 32.

    topLeft := src copy: (0 @ 0 extent: 16 @ 27).

    "Top-right: copy the Scripts pane top-right corner exactly, then pad its
    outer 6 px with the library top-right edge so the 11 px rail right edge
    below continues without a step."
    corner := src copy:
        ((src width - 16) @ 0 extent: 16 @ 27).
    libCorner := lib copy:
        ((lib width - 16) @ 0 extent: 16 @ 27).
    topRight := Form extent: 22 @ 27 depth: 32.
    topRight copyBits: (0 @ 0 corner: 16 @ 27)
        from: corner at: 0 @ 0 colorMap: nil.
    0 to: 26 do: [:ty |
        0 to: 5 do: [:tx |
            topRight pixelValueAt: (16 + tx) @ ty
                put: (libCorner pixelValueAt: (10 + tx) @ ty)]].
    "Bottom-right: the pristine native library bottom-right corner."
    bottomRight := lib copy:
        ((lib width - 21) @ (lib height - 27) extent: 21 @ 27).
    rightEdge := bottomRight copy:
        ((bottomRight width - 16) @ 0 extent: 16 @ 1).

    "Bottom-left: the native Scripts pane bottom-left corner.  It matches the
    Scripts top-left corner above it and gives a real rounded left corner."
    bottomCol := lib copy:
        ((lib width // 2) @ (lib height - 12) extent: 1 @ 12).
    bottomEdge := Form extent: 1 @ 16 depth: 32.
    4 to: 15 do: [:y |
        bottomEdge pixelValueAt: 0 @ y
            put: (bottomCol pixelValueAt: 0 @ (y - 4))].
    leftEdge := src copy:
        (0 @ (src height // 2) extent: 16 @ 1).
    curve := src copy:
        (0 @ (src height - 27) extent: 16 @ 27).
    "Expand the bottom-left corner by 16 px up and right.  The straight left
    edge and bottom edge stop at the expanded corner; the original Scripts curve
    sits at the inner bottom-left, so neither line crosses the curve."
    bottomLeft := Form extent: 32 @ 43 depth: 32.
    0 to: 15 do: [:ly |
        0 to: 15 do: [:lx |
            bottomLeft pixelValueAt: lx @ ly
                put: (leftEdge pixelValueAt: lx @ 0)]].
    0 to: 15 do: [:bx |
        0 to: 15 do: [:by |
            bottomLeft pixelValueAt: (16 + bx) @ (27 + by)
                put: (bottomEdge pixelValueAt: 0 @ by)]].
    0 to: 15 do: [:cx |
        0 to: 26 do: [:cy |
            bottomLeft pixelValueAt: cx @ (16 + cy)
                put: (curve pixelValueAt: cx @ cy)]].

    topEdge := src copy: ((src width // 2) @ 0 extent: 1 @ 16).

    self
        initFrontFromForm: frameForm
        topSectionHeight: 44.
    self instVarNamed: ''topLeftForm'' put: topLeft.
    self instVarNamed: ''topRightForm'' put: topRight.
    self instVarNamed: ''bottomLeftForm'' put: bottomLeft.
    self instVarNamed: ''bottomRightForm'' put: bottomRight.
    self instVarNamed: ''topEdgeForm'' put: topEdge.
    self instVarNamed: ''bottomEdgeForm'' put: bottomEdge.
    self instVarNamed: ''leftEdgeForm'' put: leftEdge.
    self instVarNamed: ''rightEdgeForm'' put: rightEdge.
    "6 px right margin lands the divider joint last pixel on the library
    right-edge light rim at x1313, so the tab bar is the native length and the
    outer dark rim remains visible."
    self middleBarLeftMargin: 0 rightMargin: 6.
    self color: ScratchFrameMorph palettePaneColor.
    self extent: (self class dockWidth + self class railOverlap) @ 600.
    bg := Morph new.
    bg color: ScratchFrameMorph palettePaneColor.
    self addMorphBack: bg.
    self setProperty: #railBackground toValue: bg.
    header := Morph new.
    header color: (Color r: (149/255) g: (154/255) b: (159/255)).
    self addMorph: header.
    self setProperty: #railHeader toValue: header.
    currentTab := ''Chat''.
    collapsed := false.
    pending := false.
    inputText := ''''.
    lastUsageTotal := nil.
    messages := OrderedCollection new.
    bridgeFields := OrderedCollection new.
    usageFields := OrderedCollection new.
    self setProperty: #layoutVersion toValue: 17.
    self buildTabs.
    self buildPages.
    self status: ''Ready''.
    self showCurrentTab.
    ^ self' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'extent: aPoint
    super extent: aPoint.
    self fixLayout.
    ^ self' classified: 'geometry'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'target
    "ScratchTabPaneMorph asks its target pane for a Scratch target.  A chat
    rail has none, which keeps the Costumes label branch inert."
    ^ nil' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildTabs
    | tabOn tabOff bar barSrc |
    tabPane := ScratchTabPaneMorph new.
    tabPane
        borderWidth: 0;
        "Transparent, like the native Scripts pane.  The pane background is the
        one grey behind the tabs."
        color: Color transparent;
        targetPane: self.
    "The tab pane bar is the native divided bar, cropped to its 1 px centre
    column, exactly as ScratchTabPaneMorph>>initialize builds it.  It is drawn
    under the selected tab and over the unselected tab bottoms, which is what
    makes the selected tab merge into the divider at the header/page boundary."
    barSrc := ScratchFrameMorph skinAt: #dividedImageFrameBar.
    bar := barSrc copy:
        (((barSrc width // 2) @ 0) extent: 1 @ barSrc height).
    tabPane instVarNamed: ''barForm'' put: bar.
    tabOn := ScratchFrameMorph skinAt: #tabOn.
    tabOff := ScratchFrameMorph skinAt: #tabOff.
    #(''Chat'' ''Bridge'' ''Usage'') do: [:spec |
        tabPane
            createTab: spec
            withLabel: spec localized
            onForm: tabOn
            offForm: tabOff].
    self addMorph: tabPane.
    tabPane currentTab: ''Chat''.
    topSectionHeight := 44.
    collapseButton := ToggleButton
        onForm: (ScratchFrameMorph skinAt: #deleteCircleButtonPressed)
        offForm: (ScratchFrameMorph skinAt: #deleteCircleButton).
    collapseButton
        target: self;
        actionSelector: #toggleCollapsed;
        toggleMode: false.
    self addMorph: collapseButton.
    self ensureReloadButton.
    ^ self' classified: 'initialization'.

"Dev helper: reload the UI source files and rebuild this pane.  The button only
sets a request flag; AIHarnessDevDispatcherMorph performs the reload on the UI
thread so deleting the pane is safe.  See image/39_ui_reload.st."
(Smalltalk at: #AIHarnessChatMorph) compile: 'ensureReloadButton
    | button |
    button := self valueOfProperty: #reloadButton.
    button ifNotNil: [^ button].
    button := ScratchFrameMorph
        buttonLabel: ''Reload UI'' localized
        selector: #reloadFromButton.
    button target: self.
    button width: 72; height: 18.
    self addMorph: button.
    self setProperty: #reloadButton toValue: button.
    ^ button' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'layoutReloadButton
    | button |
    button := self ensureReloadButton.
    button ifNil: [^ self].
    collapseButton ifNotNil: [
        button position:
            (collapseButton left - 6 - button width) @
                (collapseButton top - 3)].
    collapseButton ifNil: [
        button position:
            (self right - 15 - button width) @ (self top + 23)].
    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'reloadFromButton
    "Ask the dispatcher to reload 36/38/37 and rebuild the rail."
    Smalltalk at: #AIHarnessReloadUIRequested put: true.
    self status: ''Reloading UI...''.
    ^ self' classified: 'actions'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildPages
    self buildChatPage.
    self buildBridgePage.
    self buildUsagePage.
    ^ self' classified: 'initialization'.

"Native tab layering: ScratchScriptEditorMorph draws its tab pane after the
pane frame so the selected tab covers the divider.  Do the same here: skip the
tab pane in the normal submorph pass and draw it after the frame."
(Smalltalk at: #AIHarnessChatMorph) compile: 'drawSubmorphsOn: aCanvas
    submorphs reverseDo: [:m |
        (m == tabPane) ifFalse: [aCanvas fullDrawMorph: m]].
    ^ self' classified: 'drawing'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'fullDrawOn: aCanvas
    | clipC |
    self isHidden ifTrue: [^ self].
    (self hasProperty: #errorOnDraw) ifTrue: [^ self drawErrorOn: aCanvas].
    (aCanvas isVisible: self fullBounds) ifFalse: [^ self].
    clipC := aCanvas copyClipRect: self bounds truncated.
    frameInFront
        ifTrue: [
            self drawOn: clipC.
            self drawSubmorphsOn: clipC.
            self drawFrameOn: clipC.
            aCanvas fullDrawMorph: tabPane]
        ifFalse: [
            self drawOn: clipC.
            self drawSubmorphsOn: clipC].
    ^ self' classified: 'drawing'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildChatPage
    chatPage := BorderedMorph new.
    chatPage color: Color transparent.
    chatPage borderWidth: 0.
    self addMorph: chatPage.

    historyPane := ScrollFrameMorph2 new.
    historyPane color: Color transparent.
    historyPane growthFraction: 0.0.
    historyPane showHorizontalScrollbar: false.
    historyPane showVerticalScrollbar: true.
    chatPage addMorph: historyPane.

    historyMorph := AIHarnessChatHistoryMorph new.
    historyMorph color: Color transparent.
    historyPane contents: historyMorph.

    statusMorph := StringMorph new.
    statusMorph contents: ''Ready''.
    statusMorph font: (ScratchFrameMorph getFont: #Label).
    statusMorph color: Color white.
    chatPage addMorph: statusMorph.

    self buildInput.
    self buildButtons.
    ^ self' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildInput
    inputFrame := ImageFrameMorph new initFromForm: (ScratchFrameMorph skinAt: #typein).
    chatPage addMorph: inputFrame.

    inputMorph := AIHarnessChatInputMorph new.
    inputMorph borderWidth: 0.
    inputFrame addMorph: inputMorph.
    placeholderMorph := nil.
    ^ self' classified: 'initialization'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'buildButtons
    clearButton := ScratchFrameMorph
        buttonLabel: ''Clear'' localized
        selector: #clearChat.
    clearButton target: self.
    clearButton width: 64; height: 22.
    chatPage addMorph: clearButton.

    undoButton := ScratchFrameMorph
        buttonLabel: ''Undo'' localized
        selector: #undoLast.
    undoButton target: (Smalltalk at: #AIHarness).
    undoButton width: 56; height: 22.
    chatPage addMorph: undoButton.

    sendButton := ScratchFrameMorph
        buttonLabel: ''Send'' localized
        selector: #sendOrStopFromChat.
    sendButton target: (Smalltalk at: #AIHarness).
    sendButton width: 76; height: 22.
    chatPage addMorph: sendButton.
    ^ self' classified: 'initialization'.

"--- layout ---------------------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'fixLayout
    | pageLeft pageTop pageW pageH bg header |
    (tabPane isNil or: [chatPage isNil]) ifTrue: [^ self].
    "Whole-window parity, version 16.  The page reserves the native library
    right edge (11 px) and the native bottom edge (12 px)."
    pageLeft := self left.
    pageTop := self top + 44.
    pageW := (self width - 11) max: 80.
    pageH := (self bottom - 12 - pageTop) max: 80.

    "Native tab placement: pane top + topSectionHeight - tab height + 1, so the
    selected tab sits on the divided bar at the header/page boundary.  The tab
    pane is 6 px narrower than the rail so its own bar clip stops at the page
    right (x1309), not inside the 11 px right edge."
    tabPane width: (self width - 6).
    tabPane position:
        (self left + 15) @
            (self top + topSectionHeight - tabPane height + 1).
    collapseButton ifNotNil: [
        collapseButton position:
            (self right - 15 - collapseButton width) @ (self top + 24)].
    self layoutReloadButton.
    header := self valueOfProperty: #railHeader.
    header ifNotNil: [
        header position: self left @ self top.
        header extent: self width @ 44].

    chatPage position: pageLeft @ pageTop.
    chatPage extent: pageW @ pageH.
    bridgePage ifNotNil: [
        bridgePage position: pageLeft @ pageTop.
        bridgePage extent: pageW @ pageH].
    usagePage ifNotNil: [
        usagePage position: pageLeft @ pageTop.
        usagePage extent: pageW @ pageH].

    self layoutPageScrollers.
    self layoutInputArea.
    self layoutTranscriptScroll: true.
    self layoutFields: bridgeFields page: bridgePage.
    self layoutFields: usageFields page: usagePage.
    self layoutPageButtons.
    self updatePlaceholder.
    bg := self valueOfProperty: #railBackground.
    bg ifNotNil: [
        bg position: self position.
        bg extent: self extent].
    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'layoutPageScrollers
    | scroll content |
    bridgePage ifNotNil: [
        scroll := bridgePage valueOfProperty: #contentScroll.
        scroll ifNotNil: [
            scroll position: bridgePage position.
            scroll extent: bridgePage extent.
            content := bridgePage valueOfProperty: #contentMorph.
            content ifNotNil: [
                content position: bridgePage position.
                content width: bridgePage width].
            scroll updateContentsExtent.
            scroll updateScrollbars]].
    usagePage ifNotNil: [
        scroll := usagePage valueOfProperty: #contentScroll.
        scroll ifNotNil: [
            scroll position: usagePage position.
            scroll extent: usagePage extent.
            content := usagePage valueOfProperty: #contentMorph.
            content ifNotNil: [
                content position: usagePage position.
                content width: usagePage width].
            scroll updateContentsExtent.
            scroll updateScrollbars]].
    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'layoutInputArea
    | pageLeft pageTop pageW pageH rowTop buttonH inputH inputY statusY historyH statusX |
    (chatPage isNil or: [inputFrame isNil]) ifTrue: [^ self].
    pageLeft := self left.
    pageTop := self top + 44.
    pageW := (self width - 11) max: 80.
    pageH := (self bottom - 12 - pageTop) max: 80.

    buttonH := 22.
    sendButton ifNotNil: [buttonH := sendButton height].
    rowTop := pageTop + pageH - buttonH - 10.
    clearButton ifNotNil: [
        clearButton position: (pageLeft + 10) @ rowTop.
        undoButton ifNotNil: [
            undoButton position: (clearButton right + 6) @ rowTop]].
    sendButton ifNotNil: [
        sendButton position: (pageLeft + pageW - 10 - sendButton width) @ rowTop].

    inputH := 54.
    inputMorph ifNotNil: [inputH := ((inputMorph height + 10) max: 54) min: 96].
    inputY := rowTop - 8 - inputH.
    statusY := inputY - 17.
    historyH := (statusY - 4 - pageTop) max: 40.

    historyPane ifNotNil: [
        historyPane position: pageLeft @ pageTop.
        historyPane extent: pageW @ historyH].
    statusMorph ifNotNil: [
        statusX := pageLeft + ((pageW - statusMorph width) // 2).
        statusX < pageLeft ifTrue: [statusX := pageLeft].
        statusMorph position: statusX @ statusY].

    inputFrame ifNotNil: [
        inputFrame position: pageLeft @ inputY.
        inputFrame extent: pageW @ inputH].
    inputMorph ifNotNil: [
        | shift |
        shift := 0.
        (inputMorph height + 10) > inputH
            ifTrue: [shift := inputH - (inputMorph height + 10)].
        inputMorph width: (pageW - 28).
        inputMorph height: (inputMorph height max: (inputH - 12)).
        inputMorph position: (pageLeft + 14) @ (inputY + 10 + shift)].
    placeholderMorph ifNotNil: [
        placeholderMorph position: (pageLeft + 10) @ (inputY + 12)].

    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'layoutPageButtons
    | x startButton |
    bridgePage ifNotNil: [
        x := bridgePage right - 10.
        pingButton ifNotNil: [
            pingButton position: (x - pingButton width) @ (bridgePage top + 4).
            x := pingButton left - 6].
        refreshBridgeButton ifNotNil: [
            refreshBridgeButton position:
                (x - refreshBridgeButton width) @ (bridgePage top + 4).
            x := refreshBridgeButton left - 6].
        startButton := self startBridgeButton.
        startButton ifNotNil: [
            startButton position:
                (x - startButton width) @ (bridgePage top + 4)]].
    usagePage ifNotNil: [
        refreshUsageButton ifNotNil: [
            refreshUsageButton position:
                (usagePage right - 10 - refreshUsageButton width) @ (usagePage top + 4)]].
    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'layoutFields: fields page: aPage
    | content scroll x y valueX valueW headingW rowH role m label value |
    aPage ifNil: [^ self].
    content := aPage valueOfProperty: #contentMorph.
    content ifNil: [content := aPage].
    scroll := aPage valueOfProperty: #contentScroll.
    scroll ifNotNil: [scroll vScrollPixels: 0].

    x := content left + 10.
    y := content top + 8.
    valueX := content left + 132.
    valueW := (content width - 156) max: 80.
    headingW := (content width - 24) max: 80.

    fields do: [:row |
        (row isKindOf: Array)
            ifTrue: [
                role := row at: 1.
                role = #heading ifTrue: [
                    m := row at: 2.
                    m contents: m contents.
                    m fitContents.
                    m position: x @ y.
                    y := y + m height + 8]
                ifFalse: [
                role = #section ifTrue: [
                    m := row at: 2.
                    m contents: m contents.
                    m fitContents.
                    m position: x @ (y + 2).
                    y := y + m height + 7]
                ifFalse: [
                role = #row ifTrue: [
                    label := row at: 2.
                    value := row at: 3.
                    label fitContents.
                    value width: valueW.
                    value contents: value contents.
                    value fitContents.
                    rowH := label height max: value height.
                    label position: x @ y.
                    value position: valueX @ y.
                    y := y + rowH + 5]
                ifFalse: [
                role = #wide ifTrue: [
                    label := row at: 2.
                    value := row at: 3.
                    label fitContents.
                    value width: headingW.
                    value contents: value contents.
                    value fitContents.
                    label position: x @ y.
                    value position: x @ (y + label height + 2).
                    y := y + label height + 2 + value height + 5]
                ifFalse: [
                role = #note ifTrue: [
                    m := row at: 2.
                    m width: headingW.
                    m contents: m contents.
                    m fitContents.
                    m position: x @ y.
                    y := y + m height + 7]
                ifFalse: [
                role = #gap ifTrue: [
                    y := y + (row at: 2)]]]]]]]
            ifFalse: [
                m := row.
                (m isKindOf: Morph) ifTrue: [
                    m position: x @ y.
                    y := y + m height + 5]]].
    content extent: (content width) @ ((y - content top) + 8).
    scroll ifNotNil: [
        scroll updateContentsExtent.
        scroll updateScrollbars].
    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'inputChanged
    self updatePlaceholder.
    self layoutInputArea.
    historyPane ifNotNil: [historyPane updateContentsExtent].
    ^ self' classified: 'layout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'updatePlaceholder
    | empty |
    placeholderMorph ifNil: [^ self].
    empty := true.
    inputMorph ifNotNil: [empty := inputMorph contents isEmpty].
    empty
        ifTrue: [placeholderMorph isHidden: false]
        ifFalse: [placeholderMorph isHidden: true].
    ^ self' classified: 'layout'.

"--- tabs -----------------------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'currentTab
    ^ currentTab' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'tabPane
    ^ tabPane' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'chatPage
    ^ chatPage' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'bridgePage
    ^ bridgePage' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'bridgeFields
    bridgeFields ifNil: [bridgeFields := OrderedCollection new].
    ^ bridgeFields' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'usageFields
    usageFields ifNil: [usageFields := OrderedCollection new].
    ^ usageFields' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'usagePage
    ^ usagePage' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'historyPane
    ^ historyPane' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'historyMorph
    ^ historyMorph' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'inputMorph
    ^ inputMorph' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'inputFrame
    ^ inputFrame' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'inputScroller
    ^ inputScroller' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'placeholderMorph
    ^ placeholderMorph' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'statusMorph
    ^ statusMorph' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'sendButton
    ^ sendButton' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'clearButton
    ^ clearButton' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'currentCategory: aString
    currentTab := aString asString.
    self showCurrentTab.
    self fixLayout.
    ^ self' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'selectTab: aString
    "Programmatic tab selection.  Go through ScratchTabPaneMorph so the selected
    tab is lit as well as the page switched."
    (aString = ''Chat'' or: [aString = ''Bridge'' or: [aString = ''Usage'']])
        ifFalse: [^ self].
    tabPane ifNotNil: [tabPane currentTab: aString].
    ^ self' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'showCurrentTab
    "Old Morphic keeps drawing the children of a hidden morph, so switch pages
    by detaching the inactive ones instead of hiding them."
    | page |
    page := nil.
    currentTab = ''Chat'' ifTrue: [page := chatPage].
    currentTab = ''Bridge'' ifTrue: [page := bridgePage].
    currentTab = ''Usage'' ifTrue: [page := usagePage].
    page ifNil: [^ self].
    ((chatPage notNil) and: [(chatPage ~~ page) and: [chatPage owner == self]])
        ifTrue: [chatPage delete].
    ((bridgePage notNil) and: [(bridgePage ~~ page) and: [bridgePage owner == self]])
        ifTrue: [bridgePage delete].
    ((usagePage notNil) and: [(usagePage ~~ page) and: [usagePage owner == self]])
        ifTrue: [usagePage delete].
    (page owner == self) ifFalse: [self addMorph: page].
    page isHidden: false.
    self changed.
    World fullRepaintNeeded.
    currentTab = ''Bridge'' ifTrue: [self refreshBridge].
    currentTab = ''Usage'' ifTrue: [self refreshUsage].
    ^ self' classified: 'tabs'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'refreshCurrentPage
    currentTab = ''Bridge'' ifTrue: [self refreshBridge].
    currentTab = ''Usage'' ifTrue: [self refreshUsage].
    ^ self' classified: 'tabs'.

"--- status and pending ---------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'status: aString
    statusMorph ifNotNil: [
        statusMorph contents: aString asString.
        statusMorph fitContents.
        statusMorph isHidden: (aString isEmpty or: [aString asString = ''Ready'']).
        self layoutInputArea].
    ^ self' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'status
    ^ statusMorph ifNil: [''''] ifNotNil: [statusMorph contents]' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'pending
    ^ pending == true' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'pending: aBoolean
    pending := aBoolean == true.
    sendButton ifNotNil: [
        sendButton label: (pending ifTrue: [''Stop''] ifFalse: [''Send'']) localized
            font: (ScratchFrameMorph getFont: #Button).
        sendButton width: 76; height: 22].
    self layoutInputArea.
    ^ self' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'collapsed
    ^ collapsed == true' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'collapsed: aBoolean
    collapsed := aBoolean == true.
    ^ self' classified: 'status'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'toggleCollapsed
    (Smalltalk at: #AIHarness) toggleAIChat.
    ^ self' classified: 'status'.

"--- input API (compatibility with the old pane) --------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'inputText
    ^ inputText ifNil: ['''']' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'inputText: aString
    inputText := aString asString.
    ^ true' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'acceptInput
    inputMorph ifNil: [^ self].
    (inputMorph isKindOf: (Smalltalk at: #PluggableTextMorph))
        ifTrue: [inputMorph accept. ^ self].
    (inputMorph isKindOf: (Smalltalk at: #StringFieldMorph))
        ifTrue: [inputMorph acceptEdits. ^ self].
    inputMorph contents ifNotNil: [inputText := inputMorph contents asString].
    ^ self' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'clearInput
    inputText := ''''.
    inputMorph ifNotNil: [inputMorph contents: ''''.
        inputMorph height: 18].
    self updatePlaceholder.
    self fixLayout.
    ^ self' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'setInputText: aString
    inputText := aString asString.
    inputMorph ifNotNil: [inputMorph contents: inputText].
    self updatePlaceholder.
    self fixLayout.
    ^ true' classified: 'input'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'sendFromChat
    (Smalltalk at: #AIHarness) sendFromChat.
    ^ self' classified: 'input'.

"--- transcript -----------------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'messages
    messages ifNil: [messages := OrderedCollection new].
    ^ messages' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'appendLog: aString
    "Classify legacy appendLog: calls from the send/undo/apply paths."
    | text |
    text := aString asString.
    (text beginsWith: ''You: '')
        ifTrue: [^ self appendUser: (text copyFrom: 6 to: text size)].
    ((text beginsWith: ''Error:'') or: [text beginsWith: ''Problem:''])
        ifTrue: [^ self appendError: text].
    ((text beginsWith: ''Applied'') or: [
        (text beginsWith: ''Undid'') or: [text beginsWith: ''Nothing to undo'']])
        ifTrue: [^ self appendStatus: text].
    ^ self appendAssistant: text' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'appendUser: aString
    ^ self addMessage: #user text: aString' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'appendAssistant: aString
    ^ self addMessage: #assistant text: aString' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'appendStatus: aString
    ^ self addMessage: #status text: aString' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'appendError: aString
    | text |
    text := aString asString.
    (text beginsWith: ''Error:'') ifFalse: [text := ''Error: '', text].
    self status: ''Error''.
    ^ self addMessage: #error text: text' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'addMessage: role text: aString
    | entry morph |
    historyMorph ifNil: [^ nil].
    entry := AIHarnessChatMessage role: role text: aString.
    morph := self morphForMessage: entry.
    morph ifNil: [^ nil].
    historyMorph addMorph: morph.
    entry morph: morph.
    messages addLast: entry.
    self trimMessages.
    self layoutTranscriptScroll: true.
    ^ entry' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'morphForMessage: anEntry
    | role text maxW morph |
    role := anEntry role.
    text := anEntry text.
    maxW := ((historyMorph ifNil: [280] ifNotNil: [historyMorph width]) - 44) max: 100.
    role = #user ifTrue: [
        morph := AIHarnessChatBubbleMorph new.
        morph setMessage: text maxWidth: (maxW min: 230).
        ^ morph].
    role = #status ifTrue: [
        morph := StringMorph new.
        morph contents: text.
        morph font: (ScratchFrameMorph getFont: #Label).
        morph color: Color white.
        morph fitContents.
        ^ morph].
    role = #error ifTrue: [
        morph := MultilineStringMorph new.
        morph isEditable: false.
        morph textColor: Color white.
        morph color: Color transparent.
        morph borderWidth: 0.
        morph centerText: false.
        morph font: (ScratchFrameMorph getFont: #DialogBoxMessage).
        morph width: maxW.
        morph contents: ''!  '', text.
        morph fitContents.
        ^ morph].
    morph := MultilineStringMorph new.
    morph isEditable: false.
    morph textColor: Color white.
    morph color: Color transparent.
    morph borderWidth: 0.
    morph centerText: false.
    morph font: (ScratchFrameMorph getFont: #UpdatingStringField).
    morph width: maxW.
    morph contents: text.
    morph fitContents.
    ^ morph' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'trimMessages
    | oldest |
    [messages size > 200] whileTrue: [
        oldest := messages removeFirst.
        oldest morph ifNotNil: [oldest morph delete].
        oldest morph: nil].
    ^ self' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'layoutTranscriptScroll: scrollToEnd
    | atBottom scrollY |
    historyMorph ifNil: [^ self].
    scrollY := 0.
    historyPane ifNotNil: [
        scrollY := (historyPane top + historyPane borderWidth) - historyMorph top].
    atBottom := historyPane isNil or: [
        scrollY >= ((historyPane maxScroll y) - 24)].
    historyMorph width: ((historyPane ifNil: [self width - 18] ifNotNil: [historyPane width]) max: 80).
    historyMorph fixLayout.
    historyPane ifNotNil: [
        historyPane updateContentsExtent.
        historyPane updateScrollbars.
        atBottom
            ifTrue: [historyPane vScrollPixels: historyPane maxScroll y]
            ifFalse: [
                historyPane vScrollPixels:
                    ((scrollY max: 0) min: (historyPane maxScroll y))]].
    ^ self' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'logText
    | out role |
    out := WriteStream on: String new.
    self messages do: [:entry |
        role := entry role.
        role = #user ifTrue: [out nextPutAll: ''You: ''].
        role = #assistant ifTrue: [out nextPutAll: ''Scratch AI: ''].
        role = #status ifTrue: [out nextPutAll: ''Status: ''].
        role = #error ifTrue: [out nextPutAll: ''Error: ''].
        out nextPutAll: entry text; cr].
    ^ out contents' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'clearChat
    self messages do: [:entry |
        entry morph ifNotNil: [entry morph delete].
        entry morph: nil].
    messages := OrderedCollection new.
    historyMorph ifNotNil: [
        historyMorph submorphs copy do: [:m | m delete].
        historyMorph extent: (historyMorph width max: 80) @ 10].
    historyPane ifNotNil: [
        historyPane updateContentsExtent.
        historyPane vScrollPixels: 0].
    self status: ''Ready''.
    self fixLayout.
    ^ self' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'hideEmptyState
    historyMorph ifNil: [^ self].
    historyMorph submorphs copy do: [:m |
        (m valueOfProperty: #emptyState) == true
            ifTrue: [m delete]].
    ^ self' classified: 'transcript'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'showEmptyState
    | h title hints |
    h := historyMorph.
    h ifNil: [^ self].
    (h submorphs anySatisfy: [:m | (m valueOfProperty: #emptyState) == true])
        ifTrue: [^ self].
    title := StringMorph new.
    title contents: ''Ask for a change.''.
    title font: (ScratchFrameMorph getFont: #DialogBoxMessage).
    title color: Color white.
    title fitContents.
    title setProperty: #emptyState toValue: true.
    h addMorph: title.
    hints := MultilineStringMorph new.
    hints borderWidth: 0.
    hints isEditable: false.
    hints color: Color transparent.
    hints textColor: Color white.
    hints centerText: true.
    hints font: (ScratchFrameMorph getFont: #UpdatingStringField).
    hints width: 240.
    hints contents: ''Enter sends. Shift+Enter adds a line.'',
        String cr, ''Alt+V pastes. Ctrl+V opens the initials dialog.''.
    hints fitContents.
    hints setProperty: #emptyState toValue: true.
    h addMorph: hints.
    ^ self' classified: 'transcript'.

"--- small readout helpers ------------------------------------------------"
(Smalltalk at: #AIHarnessChatMorph) compile: 'textOf: aValue
    aValue ifNil: [^ ''''].
    ((aValue isKindOf: Boolean) or: [aValue isKindOf: Number])
        ifTrue: [^ aValue printString].
    ^ aValue asString' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'field: anArray at: anIndex
    (anArray isNil or: [anArray size < anIndex]) ifTrue: [^ ''''].
    ^ self textOf: (anArray at: anIndex)' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'row: aLabel value: aValue
    | label |
    label := aLabel asString, '':''.
    [label size < 19] whileTrue: [label := label, '' ''].
    ^ label, '' '', (self textOf: aValue)' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'formatCount: aNumber
    | s out first i |
    (aNumber isKindOf: Integer) ifFalse: [^ aNumber printString].
    aNumber < 0 ifTrue: [^ ''-'', (self formatCount: aNumber negated)].
    s := aNumber printString.
    out := WriteStream on: String new.
    first := s size \\ 3.
    first = 0 ifTrue: [first := 3].
    first := first min: s size.
    out nextPutAll: (s copyFrom: 1 to: first).
    i := first + 1.
    [i <= s size] whileTrue: [
        out nextPut: $,.
        out nextPutAll: (s copyFrom: i to: (i + 2 min: s size)).
        i := i + 3].
    ^ out contents' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'shorten: aString
    | s |
    s := aString asString.
    s size <= 54 ifTrue: [^ s].
    ^ (s copyFrom: 1 to: 51), ''...''' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'setPageRows: aPage fields: fields rows: rows
    | content |
    aPage ifNil: [^ self].
    content := aPage valueOfProperty: #contentMorph.
    content ifNil: [content := aPage].
    "Remove the old row morphs but leave the page buttons (Refresh/Ping) alone."
    fields do: [:row |
        (row isKindOf: Array)
            ifTrue: [
                row do: [:m |
                    ((m isKindOf: Morph) and: [m owner == content])
                        ifTrue: [m delete]]]
            ifFalse: [
                ((row isKindOf: Morph) and: [row owner == content])
                    ifTrue: [row delete]]].
    fields removeAllSuchThat: [:each | true].
    rows do: [:spec | self addPageRow: spec to: content fields: fields].
    self layoutFields: fields page: aPage.
    ^ self' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'addPageRow: spec to: content fields: fields
    | role heading label value note |
    (spec isKindOf: Morph) ifTrue: [
        "A whole row can be a composite control (for example the model
        switcher), so the caller decides its internal layout."
        content addMorph: spec.
        fields addLast: spec.
        ^ self].
    role := spec at: 1.
    role = #heading ifTrue: [
        heading := StringMorph new.
        heading contents: (spec at: 2) asString.
        heading font: (ScratchFrameMorph getFont: #DialogBoxMessage).
        heading color: Color white.
        heading fitContents.
        content addMorph: heading.
        fields addLast: (Array with: #heading with: heading).
        ^ self].
    role = #section ifTrue: [
        heading := StringMorph new.
        heading contents: (spec at: 2) asString.
        heading font: (ScratchFrameMorph getFont: #Label).
        heading color: Color white.
        heading fitContents.
        content addMorph: heading.
        fields addLast: (Array with: #section with: heading).
        ^ self].
    (role = #row or: [role = #wide]) ifTrue: [
        label := StringMorph new.
        label contents: (spec at: 2) asString, '':''.
        label font: (ScratchFrameMorph getFont: #Label).
        label color: Color white.
        label fitContents.
        content addMorph: label.
        value := MultilineStringMorph new.
        value borderWidth: 0.
        value isEditable: false.
        value color: Color transparent.
        value textColor: Color white.
        value centerText: false.
        value font: (ScratchFrameMorph getFont: #UpdatingStringField).
        value width: 120.
        value contents: (spec at: 3) asString.
        value fitContents.
        content addMorph: value.
        fields addLast: (Array with: role with: label with: value).
        ^ self].
    role = #note ifTrue: [
        note := MultilineStringMorph new.
        note borderWidth: 0.
        note isEditable: false.
        note color: Color transparent.
        note textColor: Color white.
        note centerText: false.
        note font: (ScratchFrameMorph getFont: #UpdatingStringField).
        note width: 200.
        note contents: (spec at: 2) asString.
        note fitContents.
        content addMorph: note.
        fields addLast: (Array with: #note with: note).
        ^ self].
    role = #gap ifTrue: [
        fields addLast: (Array with: #gap with: (spec at: 2))].
    ^ self' classified: 'readout'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'setPageLines: aPage fields: fields lines: lines
    "Compatibility shim: every line becomes a full-width note row."
    | rows |
    rows := lines collect: [:text | Array with: #note with: text asString].
    self setPageRows: aPage fields: fields rows: rows.
    ^ self' classified: 'readout'.

"--- class-side entry points ----------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'sendFromChat
    | pane prompt |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    pane ifNil: [^ ''error: no chat pane''].
    (pane isKindOf: AIHarnessChatMorph) ifFalse: [^ ''error: no chat pane''].
    pane pending ifTrue: [
        pane status: ''Still thinking...''.
        ^ ''error: pending''].
    pane acceptInput.
    prompt := pane inputText.
    prompt isEmpty ifTrue: [
        pane status: ''Type a prompt first''.
        ^ ''error: empty prompt''].
    pane clearInput.
    pane pending: true.
    pane status: ''Thinking...''.
    ^ self sendPromptTextAsync: prompt' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'sendOrStopFromChat
    "The Send button.  While a turn is pending it becomes Stop."
    | pane |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (pane notNil and: [
        (pane isKindOf: AIHarnessChatMorph) and: [pane pending]])
            ifTrue: [^ self cancelCurrentSend].
    ^ self sendFromChat' classified: 'chat'.

(Smalltalk at: #AIHarnessChatMorph) compile: 'testInput
    self appendUser: self inputText.
    ^ self' classified: 'actions'.

(Smalltalk at: #AIHarness) class compile: 'chatUiCompletions
    | queue |
    queue := Smalltalk at: #AIHarnessChatCompletions ifAbsent: [nil].
    queue ifNil: [
        queue := SharedQueue new.
        Smalltalk at: #AIHarnessChatCompletions put: queue].
    ^ queue' classified: 'chat ui'.

(Smalltalk at: #AIHarness) class compile: 'processChatUiCompletions
    | queue pane entry kind |
    queue := Smalltalk at: #AIHarnessChatCompletions ifAbsent: [nil].
    queue ifNil: [^ self].
    [queue isEmpty] whileFalse: [
        entry := queue next.
        pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
        (pane notNil and: [pane isKindOf: AIHarnessChatMorph]) ifTrue: [
            kind := entry at: 1.
            kind = #bridge ifTrue: [
                pane
                    applyBridgeInfo: (entry at: 2)
                    options: (entry at: 3)
                    error: (entry at: 4)].
            kind = #usage ifTrue: [
                pane applyUsageInfo: (entry at: 2) error: (entry at: 3)].
            kind = #modelSwitch ifTrue: [
                pane applyModelSwitch: (entry at: 2)].
            kind = #ping ifTrue: [
                pane applyPingResult: (entry at: 2)].
            kind = #bridgeLaunch ifTrue: [
                pane applyBridgeLaunchStatus: (entry at: 2)]]].
    ^ self' classified: 'chat ui'.

Smalltalk at: #AIHarnessChatCompletions put: SharedQueue new.

"Repair a live pane that was built before this revision: apply the palette fill
to the existing tab strip and move the Send button to the send-or-stop action.
A pane from the previous layout is rebuilt by 37_chat_dock.st instead."
[
    | pane topFill bar |
    pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (pane notNil and: [
        (pane isKindOf: AIHarnessChatMorph) and: [
            (pane valueOfProperty: #layoutVersion) = 15]]) ifTrue: [
        pane tabPane color: Color transparent.
        topFill := pane valueOfProperty: #railTopFill.
        topFill ifNotNil: [
            topFill color: ScratchFrameMorph palettePaneColor].
        bar := Form extent: (pane tabPane instVarNamed: 'barForm') extent depth: 32.
        pane tabPane instVarNamed: 'barForm' put: bar.
        pane sendButton ifNotNil: [
            pane sendButton actionSelector: #sendOrStopFromChat].
        pane pending: false.
        pane status: 'Ready'.
        pane fixLayout.
        World fullRepaintNeeded]] value.

(Smalltalk at: #AIHarness) logLine: 'chat ui classes installed'.
Transcript show: 'chat ui classes installed'; cr.
