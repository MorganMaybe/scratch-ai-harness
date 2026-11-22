"Build the harness from source.

Run this on a seed image that already has the dev loader and control server
(ScratchAI8 or later):
    python tools\ai_control.py load 00_bootstrap.st
    python tools\ai_control.py bootstrap
or:
    .\tools\build_image.ps1

Loading this file only installs the bootstrap command; it does not load the
other files yet. That matters in this old image: calling AIHarness load: from
inside a file that AIHarness load: is already evaluating aborts the outer
evaluation. The #bootstrap control command runs in a method activation, so its
nested self load: calls work.

16a_notifier is intentionally skipped: in this image its
Compiler>>evaluate:in:to:notifying:ifFail: loader returns ok without executing
the file. 17_safe_dialogs' loader (Compiler evaluate: plus the syntax global)
is the one that works and is kept."

(Smalltalk at: #AIHarness) class compile: 'bootstrap
    | bsFiles bsFailures bsResult bsLine |
    bsFiles := #(
        ''01_create_classes.st''
        ''02_compile_and_open.st''
        ''06_literal_reader.st''
        ''07_chat_ui.st''
        ''08_chat_send.st''
        ''09_undo.st''
        ''10_dev_loader.st''
        ''13_dev_server.st''
        ''14_start_server.st''
        ''15_reply_context.st''
        ''16_initials.st''
        ''17_safe_dialogs.st''
        ''17b_syntax_detail.st''
        ''17c_loader_fix.st''
        ''16b_safe_control.st''
        ''18_fix_literal_reader.st''
        ''19_labels.st''
        ''21_startup_liveness.st''
        ''22_dev_config.st''
        ''23_dialog_policy.st''
        ''24_project_files.st''
        ''25_project_registry.st''
        ''26_async_send.st''
        ''27_text_project.st''
        ''28_sprites_stage.st''
        ''29_clean_image.st''
        ''30_color_tuples.st''
        ''31_block_gaps.st''
        ''32_hats.st''
        ''33_clones.st''
        ''34_variable_targets.st''
        ''35_script_detail.st''
        ''36_chat_ui_scratch.st''
        ''38_bridge_usage_ui.st''
        ''37_chat_dock.st''
        ''39_ui_reload.st''
        ''40_release_image.st'').
    bsFailures := OrderedCollection new.
    bsFiles do: [:bsName |
        bsResult := [self load: bsName] ifError: [:e :r | ''error: '', e asString].
        bsLine := bsResult ifNil: [''nil''] ifNotNil: [bsResult asString].
        self logLine: ''bootstrap '', bsName, '' -> '', bsLine.
        ((bsLine size >= 5) and: [(bsLine copyFrom: 1 to: 5) = ''error''])
            ifTrue: [bsFailures add: bsName]].
    [self reconcileRegistry] ifError: [:e :r | nil].
    bsFailures isEmpty
        ifTrue: [self logLine: ''bootstrap complete'']
        ifFalse: [self logLine: ''bootstrap failed: '', bsFailures printString].
    ^ bsFailures isEmpty
        ifTrue: [''ok bootstrap'']
        ifFalse: [''error: bootstrap failed '', bsFailures printString]' classified: 'dev'.

"Install a minimal command handler so the caller can invoke bootstrap before
24/26 are loaded. Bootstrap replaces this handler with the full one."
(Smalltalk at: #AIHarness) class compile: 'handleDevCommand: req
    | kind |
    kind := req at: 1.
    kind = #bootstrap ifTrue: [^ self bootstrap].
    kind = #load ifTrue: [^ self load: (req at: 2)].
    kind = #status ifTrue: [^ self devStatus].
    kind = #save ifTrue: [^ self saveAs: (req at: 2)].
    ^ ''error: unknown command''' classified: 'dev server'.

(Smalltalk at: #AIHarness) logLine: 'bootstrap command installed'.
