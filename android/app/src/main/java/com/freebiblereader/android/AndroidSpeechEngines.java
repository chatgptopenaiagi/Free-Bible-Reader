package com.freebiblereader.android;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Explicit engine/voice identity. Never changes the system's default TTS engine. */
final class AndroidSpeechEngines {
    private static final int MAX_CLIENTS=8;
    private static final long INIT_TIMEOUT_MS=10000;
    private static final Handler MAIN=new Handler(Looper.getMainLooper());
    private static final Object LOCK=new Object();
    private static final LinkedHashMap<String,Client> CLIENTS=new LinkedHashMap<>(16,.75f,true);
    private static Context context;
    private static volatile Client active;
    private static volatile long cancelEpoch;
    private static volatile String selectedEngine="";
    private static final class Client {
        final String engine;
        final CountDownLatch ready=new CountDownLatch(1);
        volatile TextToSpeech tts;
        volatile int status=Integer.MIN_VALUE;
        volatile String error;
        volatile boolean closed;
        final long createdAt=SystemClock.elapsedRealtime();
        Client(String engine){this.engine=engine;}
        boolean available(){return !closed&&ready.getCount()==0&&status==TextToSpeech.SUCCESS&&tts!=null;}
    }
    static void initialize(Context owner){
        context=owner.getApplicationContext();
        selectedEngine=context.getSharedPreferences("reader-audio-native",0).getString("engine_package","");
    }
    private static void worker(){if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("SPEECH_WORKER_REQUIRED");if(context==null)throw new IllegalStateException("SPEECH_NOT_INITIALIZED");}
    private static SortedMap<String,String> discover(){
        SortedMap<String,String> result=new TreeMap<>();
        for(ResolveInfo item:context.getPackageManager().queryIntentServices(new Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE),0)){
            if(item.serviceInfo!=null&&item.serviceInfo.enabled&&item.serviceInfo.applicationInfo.enabled){String name=item.serviceInfo.packageName;CharSequence label=item.serviceInfo.loadLabel(context.getPackageManager());result.put(name,label==null?name:label.toString());}
        }
        return result;
    }
    private static String defaultEngine(){String value=Settings.Secure.getString(context.getContentResolver(),"tts_default_synth");return value==null?"":value;}
    private static Client client(String engine,boolean retry){
        synchronized(LOCK){
            Client old=CLIENTS.get(engine);
            if(old!=null&&(!retry||old.status==TextToSpeech.SUCCESS||(old.ready.getCount()!=0&&SystemClock.elapsedRealtime()-old.createdAt<INIT_TIMEOUT_MS)))return old;
            if(old!=null){CLIENTS.remove(engine);close(old);}
            if(CLIENTS.size()>=MAX_CLIENTS){Iterator<Client> iterator=CLIENTS.values().iterator();while(iterator.hasNext()){Client candidate=iterator.next();if(candidate!=active){iterator.remove();close(candidate);break;}}}
            Client created=new Client(engine);CLIENTS.put(engine,created);
            MAIN.post(()->{
                if(created.closed){created.ready.countDown();return;}
                try{
                    created.tts=new TextToSpeech(context,status->{created.status=status;if(status!=TextToSpeech.SUCCESS)created.error="ENGINE_INITIALIZATION_FAILED";created.ready.countDown();},engine);
                    if(created.closed){created.tts.stop();created.tts.shutdown();}
                }catch(Throwable error){created.status=TextToSpeech.ERROR;created.error="ENGINE_INITIALIZATION_FAILED";created.ready.countDown();}
            });
            return created;
        }
    }
    private static void close(Client client){client.closed=true;client.ready.countDown();TextToSpeech speech=client.tts;if(speech!=null)MAIN.post(()->{try{speech.stop();speech.shutdown();}catch(Exception ignored){}});}
    private static void await(Client client,long timeout)throws Exception{
        if(timeout<=0||!client.ready.await(timeout,TimeUnit.MILLISECONDS))throw new IOException("ENGINE_INITIALIZATION_TIMEOUT");
        if(!client.available())throw new IOException(client.error==null?"ENGINE_INITIALIZATION_FAILED":client.error);
    }
    static String language(String value){String lang=value==null?"":value.replace('_','-').toLowerCase(Locale.ROOT).split("-")[0];return switch(lang){case "ron","rum" -> "ro";case "eng" -> "en";case "deu","ger" -> "de";default -> lang;};}
    static String voiceId(String engine,String voice){return Uri.encode(engine)+"::"+Uri.encode(voice);}
    private static String[] resolve(JSONObject request)throws Exception{
        String id=request.optString("voice",request.optString("voice_id",""));String engine=request.optString("engine_package",request.optString("engine",""));String name=request.optString("voice_name","");
        int separator=id.indexOf("::");
        if(separator>=0){String encodedEngine=Uri.decode(id.substring(0,separator)),encodedName=Uri.decode(id.substring(separator+2));if(!engine.isEmpty()&&!engine.equals(encodedEngine))throw new IOException("VOICE_ENGINE_MISMATCH");if(!name.isEmpty()&&!name.equals(encodedName))throw new IOException("VOICE_ID_MISMATCH");engine=encodedEngine;name=encodedName;}
        else if(name.isEmpty())name=id;
        if(engine.isEmpty())throw new IOException("ENGINE_REQUIRED");if(name.isEmpty())throw new IOException("VOICE_REQUIRED");
        if(!discover().containsKey(engine))throw new IOException("ENGINE_NOT_INSTALLED");return new String[]{engine,name};
    }
    private static boolean installed(Voice voice){Set<String> features=voice.getFeatures();return features==null||!features.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED);}
    static JSONObject catalog(boolean refresh)throws Exception{
        worker();SortedMap<String,String> discovered=discover();String systemDefault=defaultEngine();
        JSONArray engines=new JSONArray(),voices=new JSONArray();List<Client> probing=new ArrayList<>();
        for(String engine:discovered.keySet()){if(probing.size()>=MAX_CLIENTS)break;probing.add(client(engine,refresh));}
        long deadline=SystemClock.elapsedRealtime()+INIT_TIMEOUT_MS;int readyCount=0;
        for(Map.Entry<String,String> entry:discovered.entrySet()){
            String engine=entry.getKey();JSONObject row=new JSONObject().put("id",engine).put("package",engine).put("engine_package",engine).put("name",entry.getValue()).put("is_default",engine.equals(systemDefault)).put("selected",engine.equals(selectedEngine));
            Client current=null;for(Client candidate:probing)if(candidate.engine.equals(engine))current=candidate;
            int count=0,romanian=0,romanianOffline=0;
            if(current==null)row.put("init_status","NOT_PROBED_LIMIT").put("error","ENGINE_PROBE_LIMIT");
            else try{
                await(current,Math.max(1,deadline-SystemClock.elapsedRealtime()));Set<Voice> actual=current.tts.getVoices();
                if(actual!=null)for(Voice voice:actual){if(count>=1024)break;boolean present=installed(voice);String locale=voice.getLocale().toLanguageTag();boolean ro=language(locale).equals("ro");if(ro&&present){romanian++;if(!voice.isNetworkConnectionRequired())romanianOffline++;}
                    voices.put(new JSONObject().put("id",voiceId(engine,voice.getName())).put("voice_name",voice.getName()).put("name",voice.getName()).put("engine_package",engine).put("engine_name",entry.getValue()).put("provider","android-native").put("language",locale).put("installed",present).put("available",present).put("runtime_available",true).put("network_required",voice.isNetworkConnectionRequired()).put("offline",!voice.isNetworkConnectionRequired()).put("quality",voice.getQuality()).put("managed",false).put("removable",false));count++;
                }
                row.put("init_status","READY").put("error",JSONObject.NULL);readyCount++;
            }catch(Throwable error){row.put("init_status",current.ready.getCount()!=0?"TIMEOUT":"FAILED").put("error",error.getMessage()==null?"ENGINE_PROBE_FAILED":error.getMessage());}
            row.put("voices_count",count).put("romanian_voice_count",romanian).put("romanian_available",romanian>0).put("romanian_offline_available",romanianOffline>0);engines.put(row);
        }
        return new JSONObject().put("platform","android").put("engines",engines).put("selected_engine",selectedEngine).put("default_engine",systemDefault).put("voices",voices).put("providers",new JSONArray().put(new JSONObject().put("id","android-native").put("available",readyCount>0).put("runtime_available",readyCount>0).put("engine_count",discovered.size())));
    }
    static JSONObject select(JSONObject request)throws Exception{
        worker();String engine=request.optString("engine_package",request.optString("engine",""));if(!discover().containsKey(engine))throw new IOException("ENGINE_NOT_INSTALLED");Client client=client(engine,true);await(client,INIT_TIMEOUT_MS);selectedEngine=engine;context.getSharedPreferences("reader-audio-native",0).edit().putString("engine_package",engine).apply();return new JSONObject().put("status","SELECTED").put("engine_package",engine);
    }
    static JSONObject synthesize(JSONObject request,File output)throws Exception{
        worker();final String[] identity=resolve(request);String expected=language(request.optString("expected_language",request.optString("language","")));if(expected.isEmpty())throw new IOException("EXPECTED_LANGUAGE_REQUIRED");
        final long epoch=cancelEpoch;Client client=client(identity[0],false);await(client,INIT_TIMEOUT_MS);if(epoch!=cancelEpoch)throw new IOException("CANCELLED");
        Voice selected=null;Set<Voice> voices=client.tts.getVoices();if(voices!=null)for(Voice voice:voices)if(voice.getName().equals(identity[1])){selected=voice;break;}
        if(selected==null||!installed(selected))throw new IOException("VOICE_NOT_AVAILABLE");if(!language(selected.getLocale().toLanguageTag()).equals(expected))throw new IOException("VOICE_LANGUAGE_MISMATCH");
        String text=request.getString("text");double speed=request.optDouble("speed",1.0);
        if(text.trim().isEmpty()||text.length()>Math.min(20000,TextToSpeech.getMaxSpeechInputLength()))throw new IOException("INVALID_SPEECH_TEXT");
        if(!Double.isFinite(speed)||speed<.5||speed>2.2)throw new IOException("INVALID_SPEECH_SPEED");
        if(client.tts.setVoice(selected)!=TextToSpeech.SUCCESS)throw new IOException("VOICE_SELECTION_FAILED");
        Voice actual=client.tts.getVoice();if(actual==null||!actual.getName().equals(identity[1])||!language(actual.getLocale().toLanguageTag()).equals(expected))throw new IOException("VOICE_READBACK_MISMATCH");
        if(client.tts.setSpeechRate((float)speed)!=TextToSpeech.SUCCESS)throw new IOException("SPEECH_RATE_REJECTED");
        CountDownLatch done=new CountDownLatch(1);AtomicInteger failure=new AtomicInteger();String utterance=UUID.randomUUID().toString();active=client;
        client.tts.setOnUtteranceProgressListener(new UtteranceProgressListener(){public void onStart(String id){}public void onDone(String id){if(id.equals(utterance))done.countDown();}public void onError(String id){if(id.equals(utterance)){failure.set(1);done.countDown();}}public void onError(String id,int error){if(id.equals(utterance)){failure.set(error==0?1:error);done.countDown();}}public void onStop(String id,boolean interrupted){if(id.equals(utterance)){failure.set(2);done.countDown();}}});
        try{
            if(epoch!=cancelEpoch)throw new IOException("CANCELLED");
            if(client.tts.synthesizeToFile(text,new Bundle(),output,utterance)!=TextToSpeech.SUCCESS)throw new IOException("SYNTHESIS_REJECTED");
            long deadline=SystemClock.elapsedRealtime()+120000;
            while(!done.await(100,TimeUnit.MILLISECONDS)){if(epoch!=cancelEpoch){client.tts.stop();throw new IOException("CANCELLED");}if(SystemClock.elapsedRealtime()>deadline){client.tts.stop();throw new IOException("SYNTHESIS_TIMEOUT");}}
            if(epoch!=cancelEpoch)throw new IOException("CANCELLED");if(failure.get()!=0)throw new IOException("ENGINE_SYNTHESIS_ERROR_"+failure.get());
            if(!output.isFile()||output.length()<=44)throw new IOException("EMPTY_AUDIO");
            actual=client.tts.getVoice();if(actual==null||!actual.getName().equals(identity[1])||!language(actual.getLocale().toLanguageTag()).equals(expected))throw new IOException("VOICE_READBACK_MISMATCH");
            return new JSONObject().put("status","COMPLETE").put("path",output.toString()).put("bytes",output.length()).put("provider","android-native").put("voice",voiceId(identity[0],identity[1])).put("voice_name",identity[1]).put("engine_package",identity[0]).put("language",actual.getLocale().toLanguageTag()).put("network_required",selected.isNetworkConnectionRequired()).put("offline",!selected.isNetworkConnectionRequired());
        }catch(Throwable error){output.delete();throw error;}finally{if(active==client)active=null;}
    }
    static void cancel(){cancelEpoch++;Client client=active;if(client!=null&&client.tts!=null)try{client.tts.stop();}catch(Exception ignored){}}
    static void shutdown(){cancel();synchronized(LOCK){for(Client client:CLIENTS.values())close(client);CLIENTS.clear();}context=null;selectedEngine="";}
}
