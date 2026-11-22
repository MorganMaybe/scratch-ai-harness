"Lazy sprite script detail for model revisions.

The normal project context carries each script's metadata, not its blocks. This
patch appends the native tuple sequence of AI-owned scripts as an optional 8th
script element, so the bridge can render exact bodies only when the model asks
for a sprite with a load_sprite request.

User scripts stay metadata-only: they are read-only, so a body would only
consume bandwidth. Colors are converted to the bridge's #(#color r g b) marker
because literalFor: cannot serialize a live Color object.

Load after 25_project_registry.st / 28_sprites_stage.st, i.e. after 34."

"Keep the current implementation (25_project_registry's id/label-aware version
in the normal order) and append detail. The guard makes a second load safe."
((Smalltalk at: #AIHarness) class includesSelector: #baseScriptContextFor:) ifFalse: [
    (Smalltalk at: #AIHarness) class methodDict
        at: #baseScriptContextFor:
        put: ((Smalltalk at: #AIHarness) class methodDict at: #scriptContextFor:)].

(Smalltalk at: #AIHarness) class compile: 'detailTuplesFor: anObject
    | out |
    (anObject isKindOf: Color) ifTrue: [
        ^ Array
            with: #color
            with: (anObject red * 255) rounded
            with: (anObject green * 255) rounded
            with: (anObject blue * 255) rounded].
    (anObject isKindOf: Array) ifTrue: [
        out := OrderedCollection new.
        anObject do: [:each | out add: (self detailTuplesFor: each)].
        ^ out asArray].
    ^ anObject' classified: 'context'.

(Smalltalk at: #AIHarness) class compile: 'scriptContextFor: aHat
    | ctx detail |
    ctx := self baseScriptContextFor: aHat.
    detail := nil.
    (ctx at: 6) ifTrue: [
        detail := [self detailTuplesFor: aHat tupleSequence]
            ifError: [:e :r | nil]].
    ^ (ctx asOrderedCollection
        add: detail;
        yourself) asArray' classified: 'context'.

(Smalltalk at: #AIHarness) logLine: 'lazy sprite script detail installed'.
Transcript show: 'lazy sprite script detail installed'; cr.
