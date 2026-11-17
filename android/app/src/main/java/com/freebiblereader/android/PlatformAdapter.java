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
    private static Object neural;
    private static final Object pickerLock=new Object();
    private static final Object speechLock=new Object();
    private static final Map<Integer,Pending> pending=new ConcurrentHashMap<>();
    private static int requestCounter=4100;
    private static class Pending {CountDownLatch latch=new CountDownLatch(1);Intent data;int result;}
    public static void initialize(MainActivity owner){activity=owner;AndroidSpeechEngines.initialize(owner);NativeAudioPlayer.initialize(owner);}
    public static String invoke(String operation,String payloadJson){
        try {
            JSONObject payload=new JSONObject(payloadJson==null||payloadJson.isEmpty()?"{}":payloadJson);
            if(Looper.myLooper()==Looper.getMainLooper()&&(operation.startsWith("picker.")||operation.equals("speech.synthesize")||operation.equals("speech.catalog")||operation.equals("speech.engine.select")))throw new IllegalStateException("Blocking native operation requires a worker thread");
            Object response=switch(operation){
                case "picker.open" -> open(payload);
                case "picker.save" -> save(payload);
                case "share" -> share(payload);
                case "settings.voices","android-voices" -> voiceSettings();
                case "speech.catalog" -> catalog(payload);
                case "speech.engine.select" -> AndroidSpeechEngines.select(payload);
                case "playback.start","playback.pause","playback.resume","playback.stop","playback.status","playback.volume" -> NativeAudioPlayer.invoke(operation,payload);
                case "speech.synthesize" -> synthesize(payload);
                case "speech.cancel" -> cancel(payload);
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
    private static JSONObject catalog(JSONObject request)throws Exception {
        JSONObject result;JSONArray diagnostics=new JSONArray();
        try{result=AndroidSpeechEngines.catalog(request.optBoolean("refresh",false));}
        catch(Throwable error){result=new JSONObject().put("platform","android").put("engines",new JSONArray()).put("voices",new JSONArray()).put("providers",new JSONArray().put(new JSONObject().put("id","android-native").put("available",false).put("error",String.valueOf(error.getMessage()))));diagnostics.put(new JSONObject().put("provider","android-native").put("error",String.valueOf(error.getMessage())));}
        JSONArray voices=result.getJSONArray("voices"),providers=result.getJSONArray("providers");
        try{Object engine=neural();if(engine!=null){JSONObject local=new JSONObject((String)engine.getClass().getMethod("voices").invoke(engine));JSONArray localVoices=local.optJSONArray("voices");if(localVoices!=null)for(int i=0;i<localVoices.length();i++)voices.put(localVoices.get(i));JSONArray localProviders=local.optJSONArray("providers");if(localProviders!=null)for(int i=0;i<localProviders.length();i++)providers.put(localProviders.get(i));}}
        catch(Throwable error){Throwable cause=error instanceof InvocationTargetException?error.getCause():error;for(String id:new String[]{"piper","espeak-ng"})providers.put(new JSONObject().put("id",id).put("available",false).put("error",String.valueOf(cause.getMessage())));diagnostics.put(new JSONObject().put("provider","bundled-native").put("error",String.valueOf(cause.getMessage())));}
        return result.put("native_playback",true).put("diagnostics",diagnostics);
    }
    private static JSONObject synthesize(JSONObject p)throws Exception {synchronized(speechLock){return synthesizeSerial(p);}}
    private static JSONObject synthesizeSerial(JSONObject p)throws Exception {
        String provider=p.optString("provider","android-native"),voice=p.optString("voice",p.optString("voice_id","")),text=p.getString("text");double speed=p.optDouble("speed",1.0);String destination=p.optString("output_path",p.optString("output",""));
        if(text.trim().isEmpty()||text.length()>20000)throw new IllegalArgumentException("INVALID_SPEECH_TEXT");
        if(!Double.isFinite(speed)||speed<.5||speed>2.2)throw new IllegalArgumentException("INVALID_SPEECH_SPEED");
        File out=new File(destination).getCanonicalFile();if(!out.getPath().startsWith(activity.getFilesDir().getCanonicalPath()+File.separator))throw new SecurityException("INVALID_AUDIO_OUTPUT_PATH");if(!out.getParentFile().isDirectory()&&!out.getParentFile().mkdirs())throw new IOException("AUDIO_FILE_NOT_WRITABLE");
        if(provider.equals("android-native"))return AndroidSpeechEngines.synthesize(p,out);
        if(!provider.equals("piper")&&!provider.equals("espeak-ng"))throw new IOException("UNSUPPORTED_SPEECH_PROVIDER");
        Object engine=neural();if(engine==null)throw new IOException("BUNDLED_SPEECH_UNAVAILABLE");
        return new JSONObject((String)engine.getClass().getMethod("synthesize",String.class,String.class,String.class,double.class,String.class,String.class,String.class).invoke(engine,provider,voice,text,speed,out.toString(),p.optString("request_id",UUID.randomUUID().toString()),p.optString("expected_language","")));
    }
    private static JSONObject cancel(JSONObject p)throws Exception{AndroidSpeechEngines.cancel();if(neural!=null){String payload=new JSONObject().put("request_id",p.optString("request_id","")).toString();neural.getClass().getMethod("invoke",String.class,String.class).invoke(neural,"speech.cancel",payload);}return new JSONObject().put("status","CANCELLED");}
    private static JSONObject quit()throws Exception {activity.runOnUiThread(()->activity.finish());return new JSONObject().put("status","CLOSING");}
    private static JSONObject persistPreferences(JSONObject p)throws Exception{JSONObject values=p.getJSONObject("values");if(values.toString().length()>1000000)throw new IllegalArgumentException("Preference storage bound exceeded");Iterator<String> keys=values.keys();while(keys.hasNext()){String key=keys.next();if(!(values.get(key) instanceof String))throw new IllegalArgumentException("Preference values must be strings");}activity.getSharedPreferences("reader-ui",0).edit().putString("values",values.toString()).apply();return new JSONObject().put("status","SAVED");}
    public static void shutdown(){try{cancel(new JSONObject());if(neural!=null)neural.getClass().getMethod("shutdown").invoke(neural);}catch(Exception ignored){}neural=null;AndroidSpeechEngines.shutdown();NativeAudioPlayer.shutdown();for(Pending p:pending.values())p.latch.countDown();pending.clear();}
}
