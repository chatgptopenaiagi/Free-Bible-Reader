package com.freebiblereader.voice.ro;

import android.app.Activity;
import android.os.*;
import android.speech.tts.*;
import android.util.Log;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Debug-only actual framework TTS client; excluded from release APKs. */
public final class VoiceProbeActivity extends Activity {
    private TextToSpeech client;
    private File folder,wave;
    private String id,text;
    private final AtomicBoolean finished=new AtomicBoolean();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private JSONObject report;
    @Override public void onCreate(Bundle state){
        super.onCreate(state);TextView screen=new TextView(this);screen.setText("Testing independent Android Romanian TTS service…");setContentView(screen);
        try{
            id=getIntent().getStringExtra("test_id");if(id==null||!id.matches("[A-Za-z0-9_-]{1,80}"))id="romanian-service";
            text=getIntent().getStringExtra("text");if(text==null)text=VoiceActivity.SAMPLE;if(text.length()>4000)throw new IllegalArgumentException("TEXT_TOO_LONG");
            folder=new File(getFilesDir(),"native-tests");folder.mkdirs();wave=new File(folder,id+".wav");
            report=new JSONObject().put("engine_package",getPackageName()).put("voice_name",RomanianTtsService.VOICE).put("test_kind","Android TextToSpeech client -> exported service -> SynthesisCallback -> framework WAV").put("audible_listening_verified",false).put("text_characters",text.length()).put("text_sha256",hash(text.getBytes(StandardCharsets.UTF_8)));
            client=new TextToSpeech(this,code->ui.post(()->ready(code)),getPackageName());
            ui.postDelayed(()->{try{if(client!=null)client.stop();complete("FAIL",new JSONObject().put("error","TIMEOUT"));}catch(Exception ignored){}},60000);
        }catch(Throwable error){fail(error);}
    }
    private void ready(int code){
        try{
            if(code!=TextToSpeech.SUCCESS)throw new IllegalStateException("ENGINE_INITIALIZATION_FAILED");
            int ro=client.isLanguageAvailable(Locale.forLanguageTag("ro-RO")),en=client.isLanguageAvailable(Locale.US);
            report.put("romanian_availability",ro).put("english_availability",en);
            if(ro<TextToSpeech.LANG_AVAILABLE||en>=TextToSpeech.LANG_AVAILABLE)throw new IllegalStateException("LANGUAGE_SCOPE_INCORRECT");
            Voice selected=null;JSONArray voices=new JSONArray();Set<Voice> available=client.getVoices();
            if(available!=null)for(Voice voice:available){voices.put(new JSONObject().put("name",voice.getName()).put("locale",voice.getLocale().toLanguageTag()).put("network_required",voice.isNetworkConnectionRequired()));if(voice.getName().equals(RomanianTtsService.VOICE))selected=voice;}
            report.put("voices",voices);
            if(selected==null||selected.isNetworkConnectionRequired()||!"ro-RO".equalsIgnoreCase(selected.getLocale().toLanguageTag()))throw new IllegalStateException("EXACT_OFFLINE_ROMANIAN_VOICE_MISSING");
            if(client.setVoice(selected)!=TextToSpeech.SUCCESS||client.getVoice()==null||!selected.getName().equals(client.getVoice().getName()))throw new IllegalStateException("EXACT_VOICE_READBACK_FAILED");
            client.setOnUtteranceProgressListener(new UtteranceProgressListener(){
                public void onStart(String value){Log.i("FBR_RO_PROBE","SYNTHESIS_START "+id);}
                public void onDone(String value){try{complete("PASS",inspect(wave));}catch(Throwable error){fail(error);}}
                public void onError(String value){fail(new IllegalStateException("FRAMEWORK_SYNTHESIS_ERROR"));}
                @Override public void onError(String value,int error){fail(new IllegalStateException("FRAMEWORK_SYNTHESIS_ERROR_"+error));}
                @Override public void onStop(String value,boolean interrupted){try{complete("STOPPED",new JSONObject().put("interrupted",interrupted));}catch(Exception error){fail(error);}}
            });
            float speed=getIntent().getFloatExtra("speed",1f);client.setSpeechRate(Math.max(.5f,Math.min(2f,speed)));
            if(client.synthesizeToFile(text,new Bundle(),wave,"ro-probe")!=TextToSpeech.SUCCESS)throw new IllegalStateException("SYNTHESIS_REQUEST_REJECTED");
            int stop=getIntent().getIntExtra("cancel_after_ms",0);if(stop>0)ui.postDelayed(()->{if(client!=null)client.stop();},stop);
        }catch(Throwable error){fail(error);}
    }
    private static long le32(RandomAccessFile file)throws IOException{return Integer.toUnsignedLong(Integer.reverseBytes(file.readInt()));}
    private static int le16(RandomAccessFile file)throws IOException{return Short.toUnsignedInt(Short.reverseBytes(file.readShort()));}
    private static String four(RandomAccessFile file)throws IOException{byte[] data=new byte[4];file.readFully(data);return new String(data,StandardCharsets.US_ASCII);}
    private static JSONObject inspect(File wave)throws Exception{
        if(!wave.isFile()||wave.length()<44||wave.length()>32000000)throw new IOException("INVALID_WAVE_SIZE");
        int rate=0,channels=0,bits=0,format=0,peak=0;long samples=0;double squared=0;
        try(RandomAccessFile file=new RandomAccessFile(wave,"r")){
            if(!"RIFF".equals(four(file)))throw new IOException("NOT_RIFF");le32(file);if(!"WAVE".equals(four(file)))throw new IOException("NOT_WAVE");
            while(file.getFilePointer()+8<=file.length()){
                String type=four(file);long size=le32(file),start=file.getFilePointer(),end=start+size;if(end>file.length())throw new IOException("TRUNCATED_WAVE");
                if(type.equals("fmt ")){format=le16(file);channels=le16(file);rate=(int)le32(file);le32(file);le16(file);bits=le16(file);}
                else if(type.equals("data")){if(size%2!=0)throw new IOException("ODD_PCM_SIZE");for(long i=0;i<size/2;i++){int value=(short)le16(file);peak=Math.max(peak,Math.abs(value));squared+=doubleValue(value)*value;samples++;}}
                file.seek(end+(size&1));
            }
        }
        if(format!=1||channels!=1||bits!=16||rate<=0||samples==0||peak==0)throw new IOException("PCM_MISSING_OR_SILENT");
        return new JSONObject().put("wave_file",wave.getName()).put("bytes",wave.length()).put("sha256",VoiceAssets.hash(wave)).put("format","PCM16LE").put("sample_rate",rate).put("channels",channels).put("samples",samples).put("duration_seconds",(double)samples/rate).put("peak",peak).put("rms",Math.sqrt(squared/samples)).put("nonzero_audio_samples",true);
    }
    private static double doubleValue(int n){return (double)n;}
    private static String hash(byte[] input)throws Exception{StringBuilder out=new StringBuilder();for(byte n:MessageDigest.getInstance("SHA-256").digest(input))out.append(String.format("%02x",n));return out.toString();}
    private void fail(Throwable error){try{complete("FAIL",new JSONObject().put("error",error.toString()));}catch(Exception ignored){Log.e("FBR_RO_PROBE","Cannot record error",error);}}
    private void complete(String status,JSONObject detail)throws Exception{
        if(!finished.compareAndSet(false,true))return;
        if(report==null)report=new JSONObject();report.put("status",status).put("result",detail);
        if(folder!=null)try(OutputStream out=new FileOutputStream(new File(folder,id+".json"))){out.write(report.toString(2).getBytes(StandardCharsets.UTF_8));}
        Log.i("FBR_RO_PROBE",status+" "+id);
        final String value=report.toString(2);ui.post(()->{TextView view=new TextView(this);view.setText(value);view.setTextIsSelectable(true);setContentView(view);});
    }
    @Override protected void onDestroy(){if(client!=null){client.stop();client.shutdown();client=null;}super.onDestroy();}
}
