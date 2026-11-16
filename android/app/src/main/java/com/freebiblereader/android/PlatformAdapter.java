package com.freebiblereader.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.speech.tts.*;
import android.media.*;
import android.util.Log;
import org.json.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.lang.reflect.*;

/** Narrow native contract; potentially blocking file dialogs always wait off the UI thread. */
public final class PlatformAdapter {
    private static MainActivity activity;
    private static TextToSpeech tts;
    private static CountDownLatch ttsReady=new CountDownLatch(1);
    private static volatile boolean ttsOk;
    private static Object neural;
    private static final Object pickerLock=new Object();
    private static final Object speechLock=new Object();
    private static final Map<Integer,Pending> pending=new ConcurrentHashMap<>();
    private static int requestCounter=4100;
    private static volatile long cancelEpoch;
    private static class Pending {CountDownLatch latch=new CountDownLatch(1);Intent data;int result;}
    public static void initialize(MainActivity owner){activity=owner;owner.runOnUiThread(()->{tts=new TextToSpeech(owner,status->{ttsOk=status==TextToSpeech.SUCCESS;ttsReady.countDown();});});}
    public static String invoke(String operation,String payloadJson){
        try {
            JSONObject payload=new JSONObject(payloadJson==null||payloadJson.isEmpty()?"{}":payloadJson);
            if(Looper.myLooper()==Looper.getMainLooper()&&(operation.startsWith("picker.")||operation.equals("speech.synthesize")))throw new IllegalStateException("Blocking native operation requires a worker thread");
            Object response=switch(operation){
                case "picker.open" -> open(payload);
                case "picker.save" -> save(payload);
                case "share" -> share(payload);
                case "settings.voices","android-voices" -> voiceSettings();
                case "speech.catalog" -> catalog();
                case "speech.synthesize" -> synthesize(payload);
                case "speech.cancel" -> cancel();
                case "app.quit" -> quit();
                case "app.info" -> new JSONObject().put("variant",BuildConfig.PRODUCT_VARIANT).put("application_id",BuildConfig.APPLICATION_ID).put("version",BuildConfig.VERSION_NAME);
                case "preferences.load" -> new JSONObject().put("values",new JSONObject(activity.getSharedPreferences("reader-ui",0).getString("values","{}")));
                case "preferences.save" -> persistPreferences(payload);
                case "document.generate" -> Class.forName("com.freebiblereader.android.AndroidDocuments").getMethod("generate",JSONObject.class).invoke(null,payload);
                case "verification.render_pdf" -> {if(!BuildConfig.DEBUG)throw new SecurityException("Debug verification only");yield Class.forName("com.freebiblereader.android.AndroidVerification").getMethod("renderPdf",JSONObject.class).invoke(null,payload);}
                default -> throw new IllegalArgumentException("Unsupported native operation: "+operation);
            };
            return response==null?"{}":response.toString();
        }catch(Throwable e){Throwable cause=e instanceof InvocationTargetException?e.getCause():e;try{return new JSONObject().put("status","ERROR").put("error",cause.getClass().getSimpleName()).put("message",String.valueOf(cause.getMessage())).toString();}catch(Exception ignored){return "{\"status\":\"ERROR\"}";}}
    }
    private static JSONObject open(JSONObject p)throws Exception {
        synchronized(pickerLock){
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Pending result=launch(intent);if(result.result!=Activity.RESULT_OK||result.data==null)return new JSONObject().put("cancelled",true);
            Uri uri=result.data.getData();if(uri==null)return new JSONObject().put("cancelled",true);
            File folder=new File(activity.getFilesDir(),"studio/staging");folder.mkdirs();String filename="import-"+UUID.randomUUID()+".db";
            try(android.database.Cursor c=activity.getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())filename=c.getString(0);}
            filename=new File(filename).getName();File target=new File(folder,UUID.randomUUID()+"-"+filename);
            try(InputStream in=activity.getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(target)){copyBounded(in,out,12L*1024*1024*1024);}
            return new JSONObject().put("cancelled",false).put("path",target.toString()).put("filename",filename).put("source_uri",uri.toString());
        }
    }
    private static JSONObject save(JSONObject p)throws Exception {
        synchronized(pickerLock){File source=privateFile(p.getString("source"));Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType(p.optString("mime","application/octet-stream")).addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,p.optString("filename",source.getName()));
            Pending result=launch(intent);if(result.result!=Activity.RESULT_OK||result.data==null||result.data.getData()==null)return new JSONObject().put("cancelled",true);
            try(InputStream in=new FileInputStream(source);OutputStream out=activity.getContentResolver().openOutputStream(result.data.getData(),"w")){copyBounded(in,out,100L*1024*1024);}
            return new JSONObject().put("cancelled",false).put("filename",p.optString("filename",source.getName())).put("bytes",source.length());}
    }
    private static JSONObject share(JSONObject p)throws Exception {
        // Native storage grant: first create a document, then share that user-owned URI.
        synchronized(pickerLock){File source=privateFile(p.getString("source"));Intent create=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType(p.optString("mime","application/octet-stream")).addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,p.optString("filename",source.getName()));Pending result=launch(create);
            if(result.result!=Activity.RESULT_OK||result.data==null||result.data.getData()==null)return new JSONObject().put("cancelled",true);Uri uri=result.data.getData();
            try(InputStream in=new FileInputStream(source);OutputStream out=activity.getContentResolver().openOutputStream(uri,"w")){copyBounded(in,out,100L*1024*1024);}
            Intent send=new Intent(Intent.ACTION_SEND).setType(p.optString("mime","application/octet-stream")).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);activity.runOnUiThread(()->activity.startActivity(Intent.createChooser(send,"Share document")));
            return new JSONObject().put("cancelled",false).put("shared",true);}
    }
    private static Pending launch(Intent intent)throws Exception {Pending result=new Pending();final int id; synchronized(pending){id=++requestCounter;pending.put(id,result);}activity.runOnUiThread(()->{try{activity.startActivityForResult(intent,id);}catch(Exception e){result.result=Activity.RESULT_CANCELED;result.latch.countDown();}});if(!result.latch.await(5,TimeUnit.MINUTES)){pending.remove(id);throw new IOException("Document picker timed out");}pending.remove(id);return result;}
    public static void activityResult(int id,int result,Intent data){Pending waiting=pending.get(id);if(waiting!=null){waiting.result=result;waiting.data=data;waiting.latch.countDown();}}
    private static void copyBounded(InputStream in,OutputStream out,long maximum)throws IOException {if(in==null||out==null)throw new IOException("Storage unavailable");byte[] buffer=new byte[262144];long total=0;int count;while((count=in.read(buffer))!=-1){total+=count;if(total>maximum)throw new IOException("File exceeds supported import/export bound");out.write(buffer,0,count);}}
    private static File privateFile(String value)throws IOException{File f=new File(value).getCanonicalFile();if(!f.getPath().startsWith(activity.getFilesDir().getCanonicalPath()+File.separator))throw new SecurityException("Only application-private files may be exported");if(!f.isFile())throw new FileNotFoundException(f.toString());return f;}
    private static JSONObject voiceSettings()throws Exception {activity.runOnUiThread(()->{try{activity.startActivity(new Intent("com.android.settings.TTS_SETTINGS"));}catch(Exception e){activity.startActivity(new Intent(Settings.ACTION_SETTINGS));}});return new JSONObject().put("status","OPENED");}
    private static Object neural()throws Exception {if(!BuildConfig.PRODUCT_VARIANT.equals("ultimate"))return null;if(neural==null)neural=Class.forName("com.freebiblereader.speech.SpeechBridge").getConstructor(android.content.Context.class).newInstance(activity);return neural;}
    private static JSONObject catalog()throws Exception {
        ttsReady.await(15,TimeUnit.SECONDS);JSONArray voices=new JSONArray();JSONArray providers=new JSONArray().put(new JSONObject().put("id","android-native").put("name","Android TextToSpeech").put("available",ttsOk).put("runtime_available",ttsOk));
        if(ttsOk&&tts.getVoices()!=null)for(Voice v:tts.getVoices()){boolean installed=!v.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED);voices.put(new JSONObject().put("id",v.getName()).put("name",v.getName()).put("provider","android-native").put("language",v.getLocale().toLanguageTag()).put("installed",installed).put("available",installed).put("runtime_available",ttsOk).put("network_required",v.isNetworkConnectionRequired()).put("offline",!v.isNetworkConnectionRequired()).put("quality",v.getQuality()));}
        Object engine=neural();if(engine!=null){JSONObject local=new JSONObject((String)engine.getClass().getMethod("voices").invoke(engine));JSONArray localVoices=local.optJSONArray("voices");if(localVoices!=null)for(int i=0;i<localVoices.length();i++)voices.put(localVoices.get(i));JSONArray localProviders=local.optJSONArray("providers");if(localProviders!=null)for(int i=0;i<localProviders.length();i++)providers.put(localProviders.get(i));}
        return new JSONObject().put("platform","android").put("providers",providers).put("voices",voices);
    }
    private static JSONObject synthesize(JSONObject p)throws Exception {synchronized(speechLock){return synthesizeSerial(p);}}
    private static JSONObject synthesizeSerial(JSONObject p)throws Exception {
        String provider=p.optString("provider","android-native"),voice=p.optString("voice",p.optString("voice_id","")),text=p.getString("text");double speed=p.optDouble("speed",1.0);String destination=p.optString("output_path",p.optString("output",""));
        if(text.length()>20000)throw new IllegalArgumentException("Narration text exceeds bound");
        File out=new File(destination).getCanonicalFile();if(!out.getPath().startsWith(activity.getFilesDir().getCanonicalPath()+File.separator))throw new SecurityException("Audio must remain in application storage");out.getParentFile().mkdirs();
        if(!provider.equals("android-native")){Object engine=neural();if(engine==null)throw new IllegalArgumentException("Neural speech is available in Ultimate only");return new JSONObject((String)engine.getClass().getMethod("synthesize",String.class,String.class,String.class,double.class,String.class).invoke(engine,provider,voice,text,speed,out.toString()));}
        ttsReady.await(15,TimeUnit.SECONDS);if(!ttsOk)throw new IOException("Android voice engine unavailable");long epoch=cancelEpoch;
        Voice selected=null;if(tts.getVoices()!=null)for(Voice v:tts.getVoices())if(v.getName().equals(voice)){selected=v;break;}if(!voice.isEmpty()&&selected==null)throw new IOException("Selected Android voice unavailable");
        if(selected!=null)tts.setVoice(selected);tts.setSpeechRate((float)Math.max(.25,Math.min(3,speed)));CountDownLatch done=new CountDownLatch(1);String utterance=UUID.randomUUID().toString();final int[] error={0};
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener(){public void onStart(String id){}public void onDone(String id){if(id.equals(utterance))done.countDown();}public void onError(String id){if(id.equals(utterance)){error[0]=1;done.countDown();}}public void onStop(String id,boolean interrupted){if(id.equals(utterance)){error[0]=2;done.countDown();}}});
        int result=tts.synthesizeToFile(text,new Bundle(),out,utterance);if(result!=TextToSpeech.SUCCESS)throw new IOException("Android speech request failed");if(!done.await(120,TimeUnit.SECONDS)){tts.stop();throw new IOException("Android speech timed out");}if(epoch!=cancelEpoch)throw new IOException("Speech cancelled");if(error[0]!=0||out.length()<44)throw new IOException("Android voice produced no WAV audio");return new JSONObject().put("status","COMPLETE").put("path",out.toString()).put("bytes",out.length()).put("provider",provider).put("voice",voice);
    }
    private static JSONObject cancel()throws Exception{cancelEpoch++;if(tts!=null)tts.stop();if(neural!=null)neural.getClass().getMethod("cancel").invoke(neural);return new JSONObject().put("status","CANCELLED");}
    private static JSONObject quit()throws Exception {activity.runOnUiThread(()->activity.finish());return new JSONObject().put("status","CLOSING");}
    private static JSONObject persistPreferences(JSONObject p)throws Exception{JSONObject values=p.getJSONObject("values");if(values.toString().length()>1000000)throw new IllegalArgumentException("Preference storage bound exceeded");Iterator<String> keys=values.keys();while(keys.hasNext()){String key=keys.next();if(!(values.get(key) instanceof String))throw new IllegalArgumentException("Preference values must be strings");}activity.getSharedPreferences("reader-ui",0).edit().putString("values",values.toString()).apply();return new JSONObject().put("status","SAVED");}
    public static void shutdown(){try{cancel();if(neural!=null)neural.getClass().getMethod("shutdown").invoke(neural);}catch(Exception ignored){}if(tts!=null){tts.shutdown();tts=null;}for(Pending p:pending.values())p.latch.countDown();pending.clear();}
}
