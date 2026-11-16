"""Speech service isolation/validation tests. Real provider samples are separate evidence."""
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
from unittest import mock
from studio import audio

class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
        self.patch=mock.patch.object(audio,'data_root',return_value=self.root)
        self.patch.start()
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()
    def test_text_and_speed_bounds_before_any_provider(self):
        for request,code in [({'text':''},'INVALID_TEXT'),({'text':'x'*25001},'INVALID_TEXT'),({'text':'a\0b'},'INVALID_TEXT'),({'text':'abc','speed':True},'INVALID_SPEED'),({'text':'abc','speed':float('nan')},'INVALID_SPEED'),({'text':'abc','speed':2.1},'INVALID_SPEED')]:
            with self.subTest(code=code),self.assertRaises(audio.AudioError) as error:audio.synthesize(request)
            self.assertEqual(error.exception.code,code)
    def test_unknown_model_and_path_traversal_rejected(self):
        for value in ['../outside','C:\\outside','not-a-registered-voice','ro_RO-mihai-medium/extra']:
            with self.subTest(value=value),self.assertRaises(audio.AudioError):audio.remove_voice(value)
    def test_pinned_manifest_sources_and_model_hashes(self):
        value=audio._manifest();self.assertEqual(len(value['voices']),3)
        for voice in value['voices']:
            self.assertEqual(len(voice['files']),3)
            for item in voice['files']:
                self.assertTrue(item['url'].startswith('https://huggingface.co/rhasspy/piper-voices/resolve/'+voice['commit']+'/'))
                self.assertRegex(item['sha256'],r'^[a-f0-9]{64}$');self.assertGreater(item['bytes'],0)
    def test_remove_preserves_unrelated_files_and_neighbor(self):
        voice=audio._voice('ro_RO-mihai-medium');folder=audio._voice_path(voice['id']);folder.mkdir()
        (folder/'unrelated-note.txt').write_text('preserve')
        with self.assertRaises(audio.AudioError) as error:audio.remove_voice(voice['id'])
        self.assertEqual(error.exception.code,'UNEXPECTED_VOICE_FILES');self.assertTrue((folder/'unrelated-note.txt').exists())
    def test_remove_only_known_managed_files(self):
        voice=audio._voice('ro_RO-mihai-medium');folder=audio._voice_path(voice['id']);folder.mkdir()
        for item in voice['files']:(folder/item['name']).write_text('owned fixture')
        (folder/'installation.json').write_text('{}');neighbor=self.root/'voices'/'user-note.txt';neighbor.write_text('keep')
        self.assertEqual(audio.remove_voice(voice['id'])['status'],'REMOVED');self.assertFalse(folder.exists());self.assertTrue(neighbor.exists())
    def test_cancelled_install_does_not_make_model_or_hold_lock(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(audio.AudioError) as error:audio.install_voice('ro_RO-mihai-medium',cancellation=cancel)
        self.assertEqual(error.exception.code,'CANCELLED');self.assertFalse(audio._work_lock.locked())
    def test_failing_download_cleans_only_staging_and_releases_lock(self):
        with mock.patch.object(audio.urllib.request,'urlopen',side_effect=OSError('offline')):
            with self.assertRaises(OSError):audio.install_voice('ro_RO-mihai-medium')
        self.assertFalse(audio._work_lock.locked());self.assertEqual(list((self.root/'voices').iterdir()),[])
    def test_work_is_serialized_without_starting_second_operation(self):
        audio._work_lock.acquire()
        try:
            with self.assertRaises(audio.AudioError) as error:audio.synthesize({'text':'Hello'})
            self.assertEqual(error.exception.code,'AUDIO_BUSY')
        finally:audio._work_lock.release()
    def test_artifact_ids_cannot_read_other_files(self):
        for value in ['../secret','a'*31,'a'*33,'C:\\secret','../../other.wav']:
            with self.subTest(value=value),self.assertRaises(audio.AudioError):audio.artifact_path(value)
    def test_wave_metadata_does_not_claim_audible_listening(self):
        path=self.root/'sample.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,16000,0,'NONE',''));wav.writeframes(b'\x01\x00'*1600)
        info=audio._wav_info(path);self.assertEqual(info['duration_seconds'],.1);self.assertTrue(info['nonzero_audio_samples'])
        self.assertNotIn('audible_listening_verified',info)
    def test_silent_and_invalid_wave_rejected(self):
        path=self.root/'zero.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,16000,0,'NONE',''));wav.writeframes(b'\x00\x00'*1600)
        with self.assertRaises(audio.AudioError):audio._wav_info(path)
        path.write_bytes(b'invalid')
        with self.assertRaises(audio.AudioError):audio._wav_info(path)
    def test_owned_child_json_response(self):
        result=audio._run_owned([sys.executable,'-c','import json;print(json.dumps({"owned":True}))'],timeout=5)
        self.assertEqual(result,{'owned':True});self.assertFalse(audio._process_lock.locked())
    def test_cancel_kills_only_owned_child(self):
        cancel=threading.Event();children=[];original=subprocess.Popen
        def capture(*args,**kwargs):
            child=original(*args,**kwargs);children.append(child);return child
        timer=threading.Timer(.15,cancel.set);timer.start()
        try:
            with mock.patch.object(audio.subprocess,'Popen',side_effect=capture),self.assertRaises(audio.AudioError) as error:
                audio._run_owned([sys.executable,'-c','import time;time.sleep(20)'],cancellation=cancel,timeout=5)
            self.assertEqual(error.exception.code,'CANCELLED');self.assertEqual(len(children),1);self.assertIsNotNone(children[0].poll());self.assertFalse(audio._process_lock.locked())
        finally:timer.cancel()
    def test_provider_timeout_is_bounded(self):
        with self.assertRaises(audio.AudioError) as error:audio._run_owned([sys.executable,'-c','import time;time.sleep(20)'],timeout=.15)
        self.assertEqual(error.exception.code,'SYNTHESIS_TIMEOUT');self.assertFalse(audio._process_lock.locked())
    def test_native_command_does_not_contain_request_values(self):
        command=audio._native_command('synthesize');self.assertNotIn('-ExecutionPolicy',command)
        self.assertIn('$env:FBR_SPEECH_REQUEST',command[-1]);self.assertNotIn(str(self.root),command[-1])
    def cache_pair(self,artifact_id,extra=None):
        folder=audio._folder('audio');(folder/(artifact_id+'.wav')).write_bytes(b'owned wave fixture')
        (folder/(artifact_id+'.json')).write_text(json.dumps({'managed_by':'free-bible-reader-audio','status':'READY','artifact_id':artifact_id,**(extra or {})}))
        return folder/(artifact_id+'.wav')
    def test_cache_prunes_old_pairs_preserving_latest_and_unrelated(self):
        old=self.cache_pair('1'*32);latest=self.cache_pair('2'*32)
        unrelated=audio._folder('audio')/'user-recording.wav';unrelated.write_bytes(b'keep')
        with mock.patch.object(audio,'MAX_CACHE_FILES',2):result=audio.prune_audio_cache()
        self.assertTrue(result['budget_met']);self.assertFalse(old.exists());self.assertTrue(latest.exists());self.assertTrue(unrelated.exists())
    def test_cache_never_deletes_unmarked_artifact_or_protected_latest(self):
        unknown=self.cache_pair('1'*32,{'managed_by':'someone-else'});latest=self.cache_pair('2'*32)
        with mock.patch.object(audio,'MAX_CACHE_FILES',0):result=audio.prune_audio_cache()
        self.assertFalse(result['budget_met']);self.assertTrue(unknown.exists());self.assertTrue(latest.exists())
    def test_cache_reservation_is_refused_when_protected_file_fills_budget(self):
        self.cache_pair('1'*32)
        with mock.patch.object(audio,'MAX_CACHE_BYTES',1):result=audio._prune_completed_cache(reserve_bytes=100,reserve_files=2)
        self.assertFalse(result['budget_met']);self.assertEqual(result['removed_artifact_ids'],[])
    def test_cache_locked_file_is_preserved_and_budget_reported(self):
        old=self.cache_pair('1'*32);self.cache_pair('2'*32);original=pathlib.Path.unlink
        def locked(path,*args,**kwargs):
            if path==old:raise PermissionError('locked')
            return original(path,*args,**kwargs)
        with mock.patch.object(audio,'MAX_CACHE_FILES',2),mock.patch.object(pathlib.Path,'unlink',locked):result=audio.prune_audio_cache()
        self.assertFalse(result['budget_met']);self.assertTrue(old.exists());self.assertEqual(result['locked_or_unavailable_artifact_ids'],['1'*32])

if __name__=='__main__':unittest.main()
