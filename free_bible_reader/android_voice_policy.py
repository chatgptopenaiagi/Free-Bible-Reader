"""Bounded, language-preserving Android speech selection; no Android imports."""
from __future__ import annotations

class SpeechError(ValueError):
    def __init__(self, code, message=None):
        self.code=code
        super().__init__(message or code)

def canonical_language(value):
    code=str(value or '').replace('_','-').casefold().split('-')[0]
    return {'ron':'ro','rum':'ro','eng':'en','deu':'de','ger':'de'}.get(code,code)

def candidates(payload, catalog):
    """At most three installed same-language candidates; never English for RO."""
    mode=payload.get('speech_mode','selected')
    if mode not in {'selected','piper','android-native','auto'}:
        raise SpeechError('INVALID_SPEECH_MODE')
    voices=[v for v in catalog.get('voices',[]) if v.get('installed') and v.get('runtime_available') is not False]
    known_requested=next((v for v in catalog.get('voices',[]) if v.get('provider')==payload.get('provider') and v.get('id')==payload.get('voice')),None)
    requested=next((v for v in voices if v.get('provider')==payload.get('provider') and v.get('id')==payload.get('voice')),None)
    # Older stored Android IDs identify a voice only in the explicitly selected
    # engine. Never resolve a colliding bare ID in another engine silently.
    engine=payload.get('engine_package') or payload.get('engine')
    if requested is None and payload.get('provider')=='android-native' and engine:
        requested=next((v for v in voices if v.get('provider')=='android-native' and v.get('engine_package')==engine and v.get('voice_name')==payload.get('voice')),None)
    expected=canonical_language(payload.get('expected_language') or payload.get('language') or (known_requested or requested or {}).get('language'))
    if not expected or expected=='und':
        raise SpeechError('SPEECH_LANGUAGE_REQUIRED','Choose the language of the text before narration.')
    same=[v for v in voices if canonical_language(v.get('language'))==expected]
    mismatch=requested is not None and canonical_language(requested.get('language'))!=expected
    if mismatch and mode!='auto':
        raise SpeechError('VOICE_LANGUAGE_MISMATCH','The selected voice does not match the text language. Choose a Romanian voice for Romanian Scripture.')
    selected=requested if not mismatch else None
    result=[]
    def add(voice):
        if voice and len(result)<3 and not any((v['provider'],v['id'])==(voice['provider'],voice['id']) for v in result):result.append(voice)
    if mode=='selected':
        if selected is None:raise SpeechError('VOICE_NOT_INSTALLED_OR_CORRUPT')
        add(selected)
    elif mode=='piper':
        voice=selected if selected and selected['provider']=='piper' else next((v for v in same if v['provider']=='piper'),None)
        if voice is None:raise SpeechError('NO_COMPATIBLE_VOICE')
        add(voice)
    elif mode=='android-native':
        system=[v for v in same if v['provider']=='android-native' and (not engine or v.get('engine_package')==engine)]
        add(selected if selected in system else next((v for v in system if v.get('network_required') is False),system[0] if system else None))
    else:
        add(selected)
        # An explicit missing preferred voice is a real failed request, not a
        # reason to silently erase the user's choice from recovery history.
        # The native provider validates its ID and reports failure before fallback.
        preferred=payload.get('voice')
        known_wrong=known_requested and canonical_language(known_requested.get('language'))!=expected
        if not result and not known_wrong and payload.get('provider') in {'piper','espeak-ng','android-native'} and isinstance(preferred,str) and 0<len(preferred)<=2048 and '\0' not in preferred:
            add({**(known_requested or {}),'provider':payload['provider'],'id':preferred,'name':(known_requested or {}).get('name',preferred),'language':expected,'engine_package':engine})
        if not result:add(next((v for v in same if v['provider']=='piper'),None))
        system=[v for v in same if v['provider']=='android-native']
        system.sort(key=lambda v:(v.get('network_required') is not False,v.get('engine_package')!='com.freebiblereader.voice.ro',bool(engine) and v.get('engine_package')!=engine))
        add(system[0] if system else None)
        add(next((v for v in same if v['provider']=='espeak-ng'),None))
        if not result:add(next(iter(same),None))
    if not result:
        raise SpeechError('NO_ROMANIAN_VOICE' if expected=='ro' else 'NO_COMPATIBLE_VOICE','No installed compatible voice was found. Open Android speech settings or install the Romanian voice add-on, then refresh voices.')
    return result, expected
