"Scratch-style AI chat rail - part 3: dock it into ScratchFrameMorph.

The core change is ScratchFrameMorph>>fixLayout, which gains a chatWidth term
and positions the pane as a child of the frame (right rail, below the top bar).
The previous body is kept verbatim as fixLayoutWithoutAIChat: that is the
rollback switch if the docked layout ever destabilizes Scratch.

Also installs:
  * AIHarness ensureDockedChat / toggleAIChat / openChat,
  * startUp docking plus a dispatcher-step safety net,
  * File > AI Chat so a collapsed rail can always be reopened.

This image's ifNil:ifNotNil: blocks take zero arguments.

Load after 36_chat_ui_scratch.st and 38_bridge_usage_ui.st.
"

"--- the old layout, verbatim, as the rollback switch ----------------------"
(Smalltalk at: #ScratchFrameMorph) compile: 'fixLayoutWithoutAIChat

	| stageExtent xyReadout w |
	stageExtent :=
		workPane isQuarterSize
			ifTrue: [workPane extent // 2]
			ifFalse: [workPane extent].

	topPane
		position: self topLeft;
		width: self width;
		height: (menuPanel height + 0 max: logoMorph height + 10).

	stageFrame
		extent: stageExtent + (14@42);
		top: topPane bottom;
		right: self right.

	workPane position: stageFrame topLeft + (4@37).

	titlePane
		position: stageFrame topLeft + (0@1);
		width: stageFrame width - 6;
		height: 36.

	self fixProjectTitleMorphLayout.

	scriptsPane fixLayout.
	w := (viewerPane catButtonsExtent x + 17)
		within: 40
		and: (self width - (scriptsPane bareMinimumWidth + stageFrame width)).
	viewerPane position: topPane bottomLeft;
		width: w;
		height: self bottom - topPane bottom.

	scriptsPane
		position: viewerPane topRight;
		width: self width - (stageFrame width + viewerPane width);
		height: self bottom - topPane bottom;
		fixLayout.

	libraryPane position: stageFrame bottomLeft;
		width: (self right - scriptsPane right);
		height: self bottom - libraryPane top.

	menuPanel
		left: logoMorph right + 18;
		top: topPane top + ((topPane height - menuPanel height) // 2) + 2.

	viewModeButtonsPanel
		right: stageFrame right - 8;
		top: self top + 7.

	stageButtonsPanel
		position: (stageFrame left + 10)@(topPane bottom + 5);
		width: stageFrame width - 28;
		height: (workPane top - stageFrame top) - 8.

	xyReadout := readoutPane submorphs at: 1.
	readoutPane
		width: xyReadout width + 23;
		height: xyReadout height + 15;
		position: stageFrame bottomRight - ((readoutPane width + 6)@3).
	xyReadout position: readoutPane position + (18@5).

	toolbarPanel
		left: (stageFrame left - 4 max: menuPanel right);
		top: self top + ((topPane height - toolbarPanel height) // 2) + 3.

	((toolbarPanel right - 5) > viewModeButtonsPanel left)
		ifTrue: [toolbarPanel delete]
		ifFalse: [
			(toolbarPanel owner = self) ifFalse: [
				self addMorphFront: toolbarPanel]].
	^ self' classified: 'layout'.

"--- docked layout: identical body plus chatWidth --------------------------"
(Smalltalk at: #ScratchFrameMorph) compile: 'fixLayout

	| stageExtent xyReadout w chatPane chatWidth railWidth overlap room |
	overlap := AIHarnessChatMorph railOverlap.
	chatPane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
	chatWidth := 0.
	railWidth := 0.
	(chatPane notNil and: [
		(chatPane isKindOf: AIHarnessChatMorph) and: [
			(chatPane owner == self) and: [chatPane collapsed not]]])
		ifTrue: [
			railWidth := chatPane width.
			chatWidth := (railWidth - overlap) max: 0].

	stageExtent :=
		workPane isQuarterSize
			ifTrue: [workPane extent // 2]
			ifFalse: [workPane extent].

	"Never squeeze the script editor below its useable minimum; the pane clamps
	itself to the room that is left on a small display."
	chatWidth > 0 ifTrue: [
		room := self width - (viewerPane catButtonsExtent x + 17)
			- (stageExtent x + 14) - scriptsPane bareMinimumWidth.
		chatWidth > room ifTrue: [chatWidth := room max: 0]].
	(chatWidth > 0 and: [railWidth ~= (chatWidth + overlap)])
		ifTrue: [chatPane width: chatWidth + overlap].

	"The native top bar spans the full window; the rail is a pane in the body
	below it.  Only the body is narrowed by chatWidth."
	topPane
		position: self topLeft;
		width: self width;
		height: (menuPanel height + 0 max: logoMorph height + 10).

	stageFrame
		extent: stageExtent + (14@42);
		top: topPane bottom;
		right: self right - chatWidth.

	workPane position: stageFrame topLeft + (4@37).

	titlePane
		position: stageFrame topLeft + (0@1);
		width: stageFrame width - 6;
		height: 36.

	self fixProjectTitleMorphLayout.

	scriptsPane fixLayout.
	w := (viewerPane catButtonsExtent x + 17)
		within: 40
		and: (self width - chatWidth - (scriptsPane bareMinimumWidth + stageFrame width)).
	viewerPane position: topPane bottomLeft;
		width: w;
		height: self bottom - topPane bottom.

	scriptsPane
		position: viewerPane topRight;
		width: self width - chatWidth - (stageFrame width + viewerPane width);
		height: self bottom - topPane bottom;
		fixLayout.

	libraryPane position: stageFrame bottomLeft;
		width: (self right - chatWidth - scriptsPane right);
		height: self bottom - libraryPane top.

	menuPanel
		left: logoMorph right + 18;
		top: topPane top + ((topPane height - menuPanel height) // 2) + 2.

	viewModeButtonsPanel
		right: stageFrame right - 8;
		top: self top + 7.

	stageButtonsPanel
		position: (stageFrame left + 10)@(topPane bottom + 5);
		width: stageFrame width - 28;
		height: (workPane top - stageFrame top) - 8.

	xyReadout := readoutPane submorphs at: 1.
	readoutPane
		width: xyReadout width + 23;
		height: xyReadout height + 15;
		position: stageFrame bottomRight - ((readoutPane width + 6)@3).
	xyReadout position: readoutPane position + (18@5).

	toolbarPanel
		left: (stageFrame left - 4 max: menuPanel right);
		top: self top + ((topPane height - toolbarPanel height) // 2) + 3.

	((toolbarPanel right - 5) > viewModeButtonsPanel left)
		ifTrue: [toolbarPanel delete]
		ifFalse: [
			(toolbarPanel owner = self) ifFalse: [
				self addMorphFront: toolbarPanel]].

	chatWidth > 0 ifTrue: [
		"Whole-window parity: the rail is a pane inside the body.  The native
		top bar spans the full window and the rail starts at its bottom."
		chatPane position: (self right - chatWidth - overlap) @ topPane bottom.
		chatPane extent: (chatWidth + overlap) @ (self height - topPane height).
		chatPane fixLayout.
		"Replicate the Scripts-pane bottom-right corner on the library corner:
		an internal corner, not the library outer window round."
		self nativeCornerOnLibrary.
		"Keep the harness rail in front of the native panes."
		(self submorphs isEmpty or: [self submorphs first ~~ chatPane])
			ifTrue: [self addMorphFront: chatPane]]
		ifFalse: [
			self restoreLibrarySeam].
	^ self' classified: 'layout'.

"Keep the rail on top on partial repaints.  ScratchFrameMorph normally draws only
the damaged native pane and returns; with the rail overlap that can repaint the
library right edge over the rail left edge.  If the damage intersects the rail,
fall through to the full submorph draw so the rail is still last."
(Smalltalk at: #ScratchFrameMorph) compile: 'fullDrawOn: aCanvas
    "Draw my full Morphic structure on the given Canvas."
    "Optimization: if damage is entirely contained in a given pane, draw only that pane."
    | damageR stageR rail |
    damageR := aCanvas clipRect.
    rail := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
    (rail notNil and: [
        (rail owner == self) and: [damageR intersects: rail bounds]])
            ifTrue: [^ super fullDrawOn: aCanvas].
    stageR := workPane bounds.
    workPane isQuarterSize ifTrue: [
        stageR := workPane position extent: (workPane width // 2) @ (workPane height // 2)].
    (stageR containsRect: damageR) ifTrue: [
        workPane fullDrawOn: aCanvas.
        ^ self].
    (scriptsPane bounds containsRect: damageR) ifTrue: [
        scriptsPane fullDrawOn: aCanvas.
        ^ self].
    (viewerPane bounds containsRect: damageR) ifTrue: [
        viewerPane fullDrawOn: aCanvas.
        ^ self].
    (readoutPane bounds containsRect: damageR) ifTrue: [
        readoutPane fullDrawOn: aCanvas.
        ^ self].
    (libraryPane bounds containsRect: damageR) ifTrue: [
        libraryPane fullDrawOn: aCanvas.
        ^ self].
    super fullDrawOn: aCanvas' classified: 'drawing'.

"--- bottom seam: native library corner at the rail ------------------------"
(Smalltalk at: #ScratchFrameMorph) compile: 'nativeCornerOnLibrary
	"While the rail is docked, copy the Scripts pane bottom-right corner
	exactly into the library bottom-right.  Add 6 px of transparent padding on
	the right so the 5 px visible Scripts edge lands in the same strip as the
	visible library right edge above (the rail covers the padding)."
	| lib original filled src corner |
	lib := libraryPane.
	lib ifNil: [^ self].
	original := lib valueOfProperty: #nativeBottomRightForm.
	original ifNil: [
		original := lib instVarNamed: ''bottomRightForm''.
		lib setProperty: #nativeBottomRightForm toValue: original].
	filled := lib valueOfProperty: #scriptRightCornerPaddedOnLibrary.
	filled ifNil: [
		src := ScratchFrameMorph skinAt: #scriptPaneFrameTransparent2.
		corner := src copy:
			((src width - 16) @ (src height - 27) extent: 16 @ 27).
		filled := Form extent: 22 @ 27 depth: 32.
		filled copyBits: (0 @ 0 corner: 16 @ 27)
			from: corner at: 0 @ 0 colorMap: nil.
		lib setProperty: #scriptRightCornerPaddedOnLibrary toValue: filled].
	(lib instVarNamed: ''bottomRightForm'') == filled ifFalse: [
		lib instVarNamed: ''bottomRightForm'' put: filled].
	^ self' classified: 'layout'.

(Smalltalk at: #ScratchFrameMorph) compile: 'restoreLibrarySeam
	"Put the native rounded corner back when the rail is collapsed and the
	library is the window outer bottom-right again."
	| lib original |
	lib := libraryPane.
	lib ifNil: [^ self].
	original := lib valueOfProperty: #nativeBottomRightForm.
	original ifNotNil: [
		(lib instVarNamed: ''bottomRightForm'') == original ifFalse: [
			lib instVarNamed: ''bottomRightForm'' put: original]].
	^ self' classified: 'layout'.

"--- menu hook ------------------------------------------------------------"
(Smalltalk at: #ScratchFrameMorph) compile: 'fileMenu: aMenuTitleMorph

	| menu |
	menu := CustomMenu new.
	menu add: ''New'' action: #newScratchProject.
	menu add: ''Open'' action: #openScratchProject.
	menu add: ''Save'' action: #saveScratchProjectNoDialog.
	menu add: ''Save As'' action: #saveScratchProject.
	menu addLine.
	menu add: ''Import Project'' action: #importScratchProject.
	menu add: ''Export Sprite'' action: #exportSprite.
	menu addLine.
	menu add: ''Project Notes'' action: #editNotes.
	menu addLine.
	menu add: ''AI Chat'' action: #toggleAIChat.
	menu add: ''Reload UI'' action: #reloadChatUIFromMenu.

	Sensor shiftPressed ifTrue: [
		menu addLine.
		menu add: ''Write Project Summary'' action: #writeSummaryFile.
		menu add: ''Write Multiple Project Summaries'' action: #writeMultipleSummaries].

	menu addLine.
	menu add: ''Quit'' action: #quitScratch.
	menu localize.

	#(2 4 5 6 7) do: [:n |
		menu labels at: n put:
			((menu labels at: n) copyFrom: 1 to: (menu labels at: n) size - 1), ScratchTranslator ellipsesSuffix].

	menu invokeOn: self at: aMenuTitleMorph bottomLeft + (0@10)' classified: 'menus'.

(Smalltalk at: #ScratchFrameMorph) compile: 'toggleAIChat
	(Smalltalk at: #AIHarness) toggleAIChat.
	^ self' classified: 'menus'.

(Smalltalk at: #ScratchFrameMorph) compile: 'reloadChatUIFromMenu
	"File > Reload UI.  The dispatcher performs the reload on the UI thread."
	Smalltalk at: #AIHarnessReloadUIRequested put: true.
	^ self' classified: 'menus'.

"--- docking lifecycle ----------------------------------------------------"
(Smalltalk at: #AIHarness) class compile: 'ensureDockedChat
	| frame pane oldWidth newWidth maxWidth |
	frame := self findFrame.
	frame ifNil: [^ nil].

	pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
	((pane notNil and: [(pane isKindOf: AIHarnessChatMorph) not]) or: [
		pane notNil and: [
			(pane isKindOf: AIHarnessChatMorph) and: [
				(pane valueOfProperty: #layoutVersion) ~= 17]]])
			ifTrue: [
				[ "retire an old floating pane or a previous rail layout"
				pane delete] ifError: [:e :r | nil].
				Smalltalk at: #AIHarnessChat put: nil.
				pane := nil].

	"Widen the frame before attaching the pane so fixLayout never has to fit a
	352 px rail into the old width."
	maxWidth := Display width - 40.
	newWidth := frame width.
	(frame width < AIHarnessChatMorph minDockFrameWidth and: [
		maxWidth >= AIHarnessChatMorph minDockFrameWidth])
			ifTrue: [newWidth := 1320].
	newWidth > maxWidth ifTrue: [newWidth := maxWidth].
	(frame width ~= newWidth) ifTrue: [
		frame extent: newWidth @ frame height].

	"Remove the custom casing/top-patch experiments from earlier builds."
	frame submorphs copy do: [:m |
		((m valueOfProperty: #railCasing) == true or: [
			(m valueOfProperty: #railTopPatch) == true or: [
				(m valueOfProperty: #railBottomPatch) == true]])
			ifTrue: [[m delete] ifError: [:e :r | nil]]].
	Smalltalk at: #AIHarnessRailCasing put: nil.
	Smalltalk at: #AIHarnessRailTopPatch put: nil.
	Smalltalk at: #AIHarnessRailBottomPatch put: nil.

	pane ifNil: [
		pane := AIHarnessChatMorph new.
		Smalltalk at: #AIHarnessChat put: pane].
	(pane owner == frame) ifFalse: [
		[pane delete] ifError: [:e :r | nil].
		frame addMorphFront: pane].
	pane isSticky: true.
	pane collapsed: false.
	pane isHidden: false.
	"Normalise a pane restored from a saved image: no saved turn can still be
	pending, and the rail should open on Chat."
	pane pending: false.
	pane status: ''Ready''.
	pane selectTab: ''Chat''.
	frame fixLayout.
	pane fixLayout.
	World fullRepaintNeeded.
	[World startSteppingSubmorphsOf: pane] ifError: [:e :r | nil].
	oldWidth := frame width.
	self logLine: ''chat docked width='', oldWidth printString.
	^ pane' classified: 'chat dock'.

(Smalltalk at: #AIHarness) class compile: 'ensureChatDocked
	| pane |
	pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
	((pane notNil) and: [
		(pane isKindOf: AIHarnessChatMorph) and: [pane owner notNil]])
			ifTrue: [^ self].
	^ [self ensureDockedChat]
		ifError: [:e :r | self logDevError: ''chat dock'' text: e asString. nil]' classified: 'chat dock'.

(Smalltalk at: #AIHarness) class compile: 'toggleAIChat
	| pane frame |
	pane := Smalltalk at: #AIHarnessChat ifAbsent: [nil].
	(pane isNil or: [(pane isKindOf: AIHarnessChatMorph) not])
		ifTrue: [^ self ensureDockedChat].
	pane collapsed: pane collapsed not.
	pane collapsed
		ifTrue: [pane isHidden: true]
		ifFalse: [pane isHidden: false].
	frame := self findFrame.
	frame ifNotNil: [frame fixLayout].
	self logLine: ''chat collapsed='', pane collapsed printString.
	^ pane' classified: 'chat dock'.

(Smalltalk at: #AIHarness) class compile: 'openChat
	^ self ensureDockedChat' classified: 'chat'.

(Smalltalk at: #AIHarness) class compile: 'startUp
	| dispatcher frame |
	self loadConfig.
	Utilities setAuthorInitials: ''ai''.
	self logLine: ''startup devMode='', self devMode printString.
	dispatcher := Smalltalk at: #AIHarnessDevDispatcher ifAbsent: [nil].
	(dispatcher isNil or: [dispatcher world isNil]) ifTrue: [
		dispatcher := (Smalltalk at: #AIHarnessDevDispatcherMorph) new.
		World addMorphFront: dispatcher.
		World startStepping: dispatcher.
		Smalltalk at: #AIHarnessDevDispatcher put: dispatcher].
	self serverAlive
		ifTrue: [
			Smalltalk at: #AIHarnessDevServerRunning put: true]
		ifFalse: [
			Smalltalk at: #AIHarnessDevServerRunning put: false.
			Smalltalk at: #AIHarnessDevHeartbeat put: 0.
			Smalltalk at: #AIHarnessDevWatchdogRunning put: false.
			self startDevServer.
			self startDevWatchdog.
			self autoOpenProject].
	[self reconcileRegistry] ifError: [:e :r | nil].
	[self ensureDockedChat] ifError: [:e :r |
		self logDevError: ''chat dock'' text: e asString].
	"Run after the snapshot resume too: the VM may leave its quit title up."
	frame := self findFrame.
	frame ifNotNil: [
		[(Delay forSeconds: 1) wait. frame updateProjectName]
			forkAt: Processor userBackgroundPriority].
	^ self' classified: 'dev server'.

"--- install / repair now -------------------------------------------------"
"Close the session-1 Phase 0 demo pane if a from-source bootstrap opened it."
(Smalltalk at: #AIHarnessPane ifAbsent: [nil])
    ifNotNil: [[(Smalltalk at: #AIHarnessPane) delete] ifError: [:e :r | nil]].
Smalltalk at: #AIHarnessPane put: nil.

[(Smalltalk at: #AIHarness) perform: #ensureDockedChat]
    ifError: [:e :r | (Smalltalk at: #AIHarness) logDevError: 'chat dock' text: e asString].

(Smalltalk at: #AIHarness) logLine: 'chat dock installed'.
Transcript show: 'chat dock installed'; cr.
