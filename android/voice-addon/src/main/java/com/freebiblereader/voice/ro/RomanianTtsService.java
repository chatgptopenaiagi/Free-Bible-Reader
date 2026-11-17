package com.freebiblereader.voice.ro;

import android.media.AudioFormat;
import android.speech.tts.*;
import android.util.Log;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** An independent offline Android engine; never redirects to a device default. */
public final class RomanianTtsService extends TextToSpeechService {
    public static final String VOICE="com.freebiblereader.voice.ro.ro-RO.espeak";
    public static final Locale LOCALE=Locale.forLanguageTag("ro-RO");
    private volatile File data;
    @Override public void onCreate(){super.onCreate();try{File path=VoiceAssets.ensure(this);if(NativeVoice.validate(path.toString()))data=path;}catch(Throwable error){Log.e("FBR_RO_TTS","Romanian resources unavailable",error);}}
    @Override protected String[] onGetLanguage(){return new String[]{"ron","ROU",""};}
    @Override protected int onIsLanguageAvailable(String language,String country,String variant){
        if(!("ro".equalsIgnoreCase(language)||"ron".equalsIgnoreCase(language)||"rum".equalsIgnoreCase(language)))return TextToSpeech.LANG_NOT_SUPPORTED;
        if(data==null)return TextToSpeech.LANG_MISSING_DATA;
        if(country==null||country.isEmpty())return TextToSpeech.LANG_AVAILABLE;
        return "RO".equalsIgnoreCase(country)||"ROU".equalsIgnoreCase(country)?TextToSpeech.LANG_COUNTRY_AVAILABLE:TextToSpeech.LANG_AVAILABLE;
    }
    @Override protected int onLoadLanguage(String language,String country,String variant){return onIsLanguageAvailable(language,country,variant);}
    @Override public List<Voice> onGetVoices(){return data==null?Collections.emptyList():Collections.singletonList(new Voice(VOICE,LOCALE,Voice.QUALITY_LOW,Voice.LATENCY_LOW,false,Collections.emptySet()));}
    @Override public String onGetDefaultVoiceNameFor(String language,String country,String variant){return onIsLanguageAvailable(language,country,variant)>=TextToSpeech.LANG_AVAILABLE?VOICE:null;}
    @Override public int onIsValidVoiceName(String name){return data!=null&&VOICE.equals(name)?TextToSpeech.SUCCESS:TextToSpeech.ERROR;}
    @Override public int onLoadVoice(String name){return onIsValidVoiceName(name);}
    @Override protected Set<String> onGetFeaturesForLanguage(String language,String country,String variant){return Collections.emptySet();}
    @Override protected void onStop(){NativeVoice.cancel();}
    @Override protected void onSynthesizeText(SynthesisRequest request,SynthesisCallback callback){
        try{
            if(data==null){callback.error(TextToSpeech.ERROR_NOT_INSTALLED_YET);return;}
            String voice=request.getVoiceName();
            if((voice!=null&&!voice.isEmpty()&&!VOICE.equals(voice))||onIsLanguageAvailable(request.getLanguage(),request.getCountry(),request.getVariant())<0){callback.error(TextToSpeech.ERROR_INVALID_REQUEST);return;}
            CharSequence value=request.getCharSequenceText();String text=value==null?"":value.toString();
            if(text.isEmpty()||text.length()>4000||text.indexOf('\0')>=0){callback.error(TextToSpeech.ERROR_INVALID_REQUEST);return;}
            long token=NativeVoice.begin();long samples=NativeVoice.synthesize(data.toString(),text.getBytes(StandardCharsets.UTF_8),Math.max(80,Math.min(450,175*request.getSpeechRate()/100)),Math.max(0,Math.min(99,50*request.getPitch()/100)),new PcmSink(callback),token);
            if(samples>0)Log.i("FBR_RO_TTS","SYNTHESIS_DONE voice="+VOICE+" chars="+text.length()+" samples="+samples);
        }catch(Throwable error){Log.e("FBR_RO_TTS","Synthesis failed",error);if(!callback.hasFinished())callback.error(TextToSpeech.ERROR_SYNTHESIS);}
        finally{if(!callback.hasFinished())callback.done();}
    }
    public static final class PcmSink {
        private final SynthesisCallback callback;
        PcmSink(SynthesisCallback callback){this.callback=callback;}
        public boolean start(int rate){return callback.start(rate,AudioFormat.ENCODING_PCM_16BIT,1)==TextToSpeech.SUCCESS;}
        public boolean audio(byte[] bytes){int max=callback.getMaxBufferSize()&~1;if(max<2)return false;for(int offset=0;offset<bytes.length;offset+=max)if(callback.audioAvailable(bytes,offset,Math.min(max,bytes.length-offset))!=TextToSpeech.SUCCESS)return false;return true;}
    }
}
