package com.freebiblereader.voice.ro;
import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import java.util.ArrayList;
import java.util.Collections;

public final class VoiceDataActivity extends Activity {
    @Override public void onCreate(Bundle state){
        super.onCreate(state);Intent result=new Intent();
        if(TextToSpeech.Engine.ACTION_GET_SAMPLE_TEXT.equals(getIntent().getAction())){
            result.putExtra(TextToSpeech.Engine.EXTRA_SAMPLE_TEXT,VoiceActivity.SAMPLE);setResult(TextToSpeech.LANG_COUNTRY_AVAILABLE,result);
        }else{
            boolean ready=false;try{ready=NativeVoice.validate(VoiceAssets.ensure(this).toString());}catch(Throwable ignored){}
            result.putStringArrayListExtra(TextToSpeech.Engine.EXTRA_AVAILABLE_VOICES,new ArrayList<>(ready?Collections.singletonList("ron-ROU"):Collections.emptyList()));
            result.putStringArrayListExtra(TextToSpeech.Engine.EXTRA_UNAVAILABLE_VOICES,new ArrayList<>(ready?Collections.emptyList():Collections.singletonList("ron-ROU")));
            setResult(ready?TextToSpeech.Engine.CHECK_VOICE_DATA_PASS:TextToSpeech.Engine.CHECK_VOICE_DATA_FAIL,result);
        }
        finish();
    }
}
