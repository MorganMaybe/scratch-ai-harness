(Smalltalk includesKey: #AIHarnessPaneMorph) ifFalse: [
    BorderedMorph subclass: #AIHarnessPaneMorph
        instanceVariableNames: 'logMorph'
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].

(Smalltalk includesKey: #AIHarness) ifFalse: [
    Object subclass: #AIHarness
        instanceVariableNames: ''
        classVariableNames: ''
        poolDictionaries: ''
        category: 'Scratch-AI'].
