"""Android voice policy and generation/playback boundaries; no device claims.

All profiles are temporary. Native calls are replaced by controlled callbacks;
successful synthesis writes a real short, non-silent PCM WAV, not a placeholder.
"""
from __future__ import annotations
import copy
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import threading
import types
import unittest
import wave
from unittest import mock

from free_bible_reader import android_runtime as runtime
from free_bible_reader.android_voice_policy import SpeechError, candidates
from studio import paths


def pcm_file(path, *, silent=False):
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(target),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(22050)
        output.writeframes(b''.join(struct.pack('<h',0 if silent else round(6000*math.sin(2*math.pi*440*i/22050))) for i in range(4410)))


def catalog():
    return {'native_playback':True,'voices':[
        {'provider':'piper','id':'en_US-joe-medium','name':'Joe','language':'en-US','installed':True,'runtime_available':None},
        {'provider':'piper','id':'ro_RO-mihai-medium','name':'Mihai','language':'ro-RO','installed':True,'runtime_available':None},
        {'provider':'android-native','id':'com.freebiblereader.voice.ro::com.freebiblereader.voice.ro.ro-RO.espeak','voice_name':'com.freebiblereader.voice.ro.ro-RO.espeak','engine_package':'com.freebiblereader.voice.ro','name':'Romanian compact','language':'ro-RO','network_required':False,'installed':True,'runtime_available':True},
        {'provider':'espeak-ng','id':'ro','name':'Romanian eSpeak','language':'ro','installed':True,'runtime_available':None},
        {'provider':'android-native','id':'other.engine::ro-network','voice_name':'ro-network','engine_package':'other.engine','name':'Romanian network','language':'ron','network_required':True,'installed':True,'runtime_available':True},
        {'provider':'piper','id':'de_DE-thorsten-medium','name':'Thorsten','language':'de-DE','installed':True,'runtime_available':True},
    ]}


class AndroidSpeechRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='fbr005-speech-test-')
        self.profile=Path(self.temporary.name)
        self.environment=mock.patch.dict(os.environ,{'FBR_STUDIO_DIR':str(self.profile)})
        self.environment.start()
        self.configured=mock.patch.object(paths,'_configured_root',None)
        self.configured.start()
        runtime._narration_paused.clear()
        self.calls=[];self.progress=[]

    def tearDown(self):
        runtime._narration_paused.clear()
        self.configured.stop();self.environment.stop();self.temporary.cleanup()

    def request(self, **changes):
        return {'text':'Fiindcă atât de mult a iubit Dumnezeu lumea.','provider':'piper','voice':'ro_RO-mihai-medium','expected_language':'ron','speed':1,'volume':.7,'speech_mode':'selected',**changes}

    def native(self, operation, payload=None):
        self.calls.append((operation,copy.deepcopy(payload)))
        if operation=='speech.catalog':return catalog()
        if operation=='speech.synthesize':
            pcm_file(payload['output_path'])
            return {'provider':payload['provider'],'voice':payload['voice'],'language':payload['expected_language']}
        if operation=='playback.start':return {'state':'preparing','playback_id':37,'completed':False}
        if operation=='playback.status':return {'state':'completed','playback_id':37,'completed':True,'duration_ms':200,'position_ms':200}
        if operation=='playback.stop':return {'state':'stopped','playback_id':37,'completed':False}
        if operation=='speech.cancel':return {'status':'CANCELLED'}
        raise AssertionError('Unexpected native operation '+operation)

    def run_request(self, request=None, *, native=None, narration=False, cancellation=None):
        with mock.patch.object(runtime,'_invoke',side_effect=native or self.native):
            return runtime._synthesize(request or self.request(),cancellation or threading.Event(),lambda **value:self.progress.append(value),narration=narration)

    def test_romanian_text_rejects_saved_english_joe_before_native_synthesis(self):
        with self.assertRaises(SpeechError) as error:
            self.run_request(self.request(voice='en_US-joe-medium'))
        self.assertEqual(error.exception.code,'VOICE_LANGUAGE_MISMATCH')
        self.assertEqual([call[0] for call in self.calls],['speech.catalog'])
        self.assertFalse(list(self.profile.rglob('*.wav')))

    def test_auto_candidates_are_bounded_deduplicated_and_same_language(self):
        options,language=candidates(self.request(speech_mode='auto',voice='en_US-joe-medium'),catalog())
        self.assertEqual(language,'ro');self.assertEqual(len(options),3)
        self.assertEqual({voice['provider'] for voice in options},{'piper','android-native','espeak-ng'})
        self.assertEqual(len({(voice['provider'],voice['id']) for voice in options}),3)
        self.assertNotIn('en_US-joe-medium',[voice['id'] for voice in options])

    def test_engine_specific_android_choice_does_not_resolve_a_colliding_other_engine(self):
        value=catalog();voice=value['voices'][2]
        value['voices'].append({**voice,'id':'other.engine::'+voice['voice_name'],'engine_package':'other.engine'})
        options,_=candidates(self.request(provider='android-native',voice=voice['voice_name'],engine_package=voice['engine_package']),value)
        self.assertEqual(options[0]['engine_package'],'com.freebiblereader.voice.ro')

    def test_failed_neural_attempt_records_actual_successful_provider_and_engine(self):
        def callback(operation,payload=None):
            if operation=='speech.synthesize' and payload['provider']=='piper':
                self.calls.append((operation,copy.deepcopy(payload)));raise SpeechError('MODEL_LOAD_FAILED')
            return self.native(operation,payload)
        result=self.run_request(self.request(speech_mode='auto'),native=callback)
        self.assertEqual(result['provider'],'android-native');self.assertEqual(result['engine_package'],'com.freebiblereader.voice.ro')
        self.assertEqual(result['expected_language'],'ro');self.assertTrue(result['fallback_used'])
        self.assertEqual([(row['provider'],row['status']) for row in result['attempts']],[('piper','FAILED'),('android-native','COMPLETE')])
        self.assertEqual(result['native']['provider'],'android-native')
        request=[payload for operation,payload in self.calls if operation=='speech.synthesize'][-1]
        self.assertEqual(request['engine_package'],'com.freebiblereader.voice.ro');self.assertEqual(request['expected_language'],'ro')

    def test_auto_never_attempts_more_than_three_even_when_all_fail(self):
        def callback(operation,payload=None):
            if operation=='speech.synthesize':self.calls.append((operation,copy.deepcopy(payload)));raise SpeechError('ENGINE_FAILURE')
            return self.native(operation,payload)
        with self.assertRaises(SpeechError) as error:self.run_request(self.request(speech_mode='auto'),native=callback)
        self.assertEqual(error.exception.code,'SPEECH_RECOVERY_FAILED')
        attempts=[payload for operation,payload in self.calls if operation=='speech.synthesize']
        self.assertEqual(len(attempts),3);self.assertTrue(all(row['expected_language']=='ro' for row in attempts))
        self.assertFalse(list(self.profile.rglob('*.wav')))

    def test_explicit_cancellation_never_falls_back(self):
        for code in ['SPEECH_CANCELLED','CANCELLED']:
            with self.subTest(code=code):
                self.calls.clear()
                def callback(operation,payload=None):
                    if operation=='speech.synthesize':self.calls.append((operation,copy.deepcopy(payload)));raise SpeechError(code)
                    return self.native(operation,payload)
                with self.assertRaises(SpeechError) as error:self.run_request(self.request(speech_mode='auto'),native=callback)
                self.assertIn(error.exception.code,{'CANCELLED','SPEECH_CANCELLED'})
                self.assertEqual(len([row for row in self.calls if row[0]=='speech.synthesize']),1)

    def test_java_cancellation_message_becomes_a_stable_cancellation_code(self):
        class Platform:
            @staticmethod
            def invoke(operation,payload):return json.dumps({'status':'ERROR','error':'IOException','message':'CANCELLED'})
        with mock.patch.dict('sys.modules',{'java':types.SimpleNamespace(jclass=lambda name:Platform)}):
            with self.assertRaises(SpeechError) as error:runtime._invoke('speech.synthesize',{})
        self.assertIn(error.exception.code,{'CANCELLED','SPEECH_CANCELLED'})

    def test_cancel_event_prevents_first_attempt_and_releases_lock(self):
        cancellation=threading.Event();cancellation.set()
        with self.assertRaises(SpeechError) as error:self.run_request(self.request(speech_mode='auto'),cancellation=cancellation)
        self.assertEqual(error.exception.code,'SPEECH_CANCELLED')
        self.assertFalse(any(operation=='speech.synthesize' for operation,_ in self.calls))
        self.assertFalse(runtime._speech_lock.locked())

    def test_generated_wav_is_ready_but_not_completed_narration(self):
        result=self.run_request()
        self.assertEqual(result['status'],'READY');self.assertFalse(result['narration_completed'])
        self.assertTrue(result['nonzero_audio_samples']);self.assertEqual(result['duration_seconds'],.2)
        self.assertFalse(any(operation.startswith('playback.') for operation,_ in self.calls))
        with wave.open(str(self.profile/'audio'/(result['artifact_id']+'.wav')),'rb') as audio:self.assertEqual(audio.getnframes(),4410)

    def test_narration_waits_for_matching_native_player_completion(self):
        statuses=iter([{'state':'playing','playback_id':37,'completed':False,'position_ms':20},
                       {'state':'completed','playback_id':37,'completed':True,'position_ms':200,'duration_ms':200}])
        def callback(operation,payload=None):
            if operation=='playback.status':self.calls.append((operation,payload));return next(statuses)
            return self.native(operation,payload)
        result=self.run_request(native=callback,narration=True)
        self.assertEqual(result['status'],'COMPLETE');self.assertTrue(result['narration_completed'])
        self.assertFalse(result['human_listening_verified']);self.assertEqual(result['playback_id'],37)
        self.assertEqual(len([row for row in self.calls if row[0]=='playback.status']),2)

    def test_replaced_player_cannot_be_reported_as_this_passage_completed(self):
        def callback(operation,payload=None):
            if operation=='playback.status':self.calls.append((operation,payload));return {'state':'completed','playback_id':99,'completed':True}
            return self.native(operation,payload)
        with self.assertRaises(SpeechError) as error:self.run_request(native=callback,narration=True)
        self.assertEqual(error.exception.code,'PLAYBACK_REPLACED')
        self.assertTrue(any(operation=='playback.stop' for operation,_ in self.calls))
        self.assertFalse(list(self.profile.rglob('*.wav')))

    def test_silent_pcm_is_rejected_instead_of_counted_as_working_audio(self):
        def callback(operation,payload=None):
            if operation=='speech.synthesize':self.calls.append((operation,copy.deepcopy(payload)));pcm_file(payload['output_path'],silent=True);return {'provider':'piper'}
            return self.native(operation,payload)
        with self.assertRaises(SpeechError) as error:self.run_request(native=callback)
        self.assertEqual(error.exception.code,'SILENT_NATIVE_AUDIO_OUTPUT')
        self.assertFalse(list(self.profile.rglob('*.wav')))


if __name__=='__main__':unittest.main()
