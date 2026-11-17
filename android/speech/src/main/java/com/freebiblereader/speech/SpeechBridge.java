package com.freebiblereader.speech;

import android.content.Context;
import android.content.res.AssetManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.atomic.AtomicReference;

/** Native offline providers. Invoked from a bounded backend worker, never the UI thread. */
public final class SpeechBridge {
    private static volatile SpeechBridge instance;
    private static final String ASSETS="fbr-speech/";
    private final Context context;
    private final File root;
    private final AtomicReference<String> activeRequest=new AtomicReference<>();
    private final Object requestLock=new Object();
    private final java.util.LinkedHashSet<String> cancelledRequests=new java.util.LinkedHashSet<>();
    private JSONObject manifest;
    private String failure;
    private boolean prepared;
    private volatile boolean nativeLoaded;
    private volatile String nativeFailure;
    private final java.util.HashSet<String> preparedVoices=new java.util.HashSet<>();
    private final java.util.Set<String> testedVoices=java.util.concurrent.ConcurrentHashMap.newKeySet();
    public SpeechBridge(Context context){this.context=context.getApplicationContext();root=new File(this.context.getFilesDir(),"speech");}
    public static SpeechBridge get(Context context){
        if(instance==null)synchronized(SpeechBridge.class){if(instance==null)instance=new SpeechBridge(context);}
        return instance;
    }
    public static String invoke(Context context,String operation,String payload){return get(context).invoke(operation,payload);}
    public String invoke(String operation,String payload){
        try{
            JSONObject p=new JSONObject(payload==null||payload.trim().isEmpty()?"{}":payload);
            return switch(operation){
                case "speech.catalog" -> voices();
                case "speech.synthesize" -> synthesize(p.getString("provider"),p.getString("voice"),p.getString("text"),p.optDouble("speed",1),p.getString("output_path"),p.optString("request_id","speech"));
                case "speech.cancel" -> {String id=p.optString("request_id","");synchronized(requestLock){if(!id.isEmpty()){cancelledRequests.add(id);while(cancelledRequests.size()>64)cancelledRequests.remove(cancelledRequests.iterator().next());}if(id.isEmpty()||id.equals(activeRequest.get()))cancel();}yield new JSONObject().put("cancelled",true).toString();}
                default -> throw new IllegalArgumentException("UNSUPPORTED_SPEECH_OPERATION");
            };
        }catch(Throwable e){return error(e).toString();}
    }
    private static JSONObject error(Throwable e){
        try{return new JSONObject().put("error",new JSONObject().put("code",e.getMessage()==null?"SPEECH_ERROR":e.getMessage()).put("message","Offline speech operation could not be completed."));}
        catch(Exception ignored){throw new IllegalStateException("SPEECH_ERROR");}
    }
    private synchronized void prepare() throws Exception {
        if(prepared)return;failure=null;
        try{
            AssetManager assets=context.getAssets();
            try(InputStream input=assets.open(ASSETS+"asset-manifest.json");ByteArrayOutputStream body=new ByteArrayOutputStream()){byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))!=-1)body.write(buffer,0,n);manifest=new JSONObject(body.toString(StandardCharsets.UTF_8.name()));}
            if(!root.isDirectory()&&!root.mkdirs())throw new IOException("SPEECH_STORAGE_UNAVAILABLE");
            JSONArray files=manifest.getJSONArray("files");
            for(int i=0;i<files.length();i++){
                JSONObject item=files.getJSONObject(i);
                // A missing Piper model must not disable independently usable eSpeak data.
                if(!item.getString("path").startsWith("voices/"))ensureAsset(item);
            }
            prepared=true;
        }catch(Throwable e){failure=e.getMessage()==null?"SPEECH_RUNTIME_UNAVAILABLE":e.getMessage();throw e;}
    }
    private synchronized void loadNative(){
        if(nativeLoaded)return;
        try{System.loadLibrary("piper_jni");nativeLoaded=true;nativeFailure=null;}
        catch(Throwable error){nativeFailure="NATIVE_SPEECH_INITIALIZATION_FAILED";throw error;}
    }
    private void ensureAsset(JSONObject item)throws Exception{
        String relative=item.getString("path");File target=safeFile(relative);
        if(target.isFile()&&target.length()==item.getLong("bytes")&&sha256(target).equals(item.getString("sha256")))return;
        File parent=target.getParentFile();if(!parent.isDirectory()&&!parent.mkdirs())throw new IOException("SPEECH_STORAGE_UNAVAILABLE");File pending=new File(parent,target.getName()+".part");
        try(InputStream in=context.getAssets().open(ASSETS+relative);OutputStream out=new BufferedOutputStream(new FileOutputStream(pending))){byte[] buffer=new byte[1024*1024];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);}
        if(pending.length()!=item.getLong("bytes")||!sha256(pending).equals(item.getString("sha256"))){pending.delete();throw new IOException("SPEECH_RESOURCE_INTEGRITY_FAILED");}
        if(target.exists()&&!target.delete())throw new IOException("SPEECH_RESOURCE_REPLACE_FAILED");if(!pending.renameTo(target))throw new IOException("SPEECH_RESOURCE_REPLACE_FAILED");
    }
    private synchronized void prepareVoice(String voice)throws Exception{
        if(preparedVoices.contains(voice))return;String prefix="voices/"+voice+"/";int count=0;JSONArray files=manifest.getJSONArray("files");
        for(int i=0;i<files.length();i++){JSONObject item=files.getJSONObject(i);if(item.getString("path").startsWith(prefix)){ensureAsset(item);count++;}}
        if(count<2)throw new IOException("VOICE_NOT_INSTALLED_OR_CORRUPT");preparedVoices.add(voice);
    }
    private File safeFile(String relative) throws IOException{
        File file=new File(root,relative);String prefix=root.getCanonicalPath()+File.separator;
        if(!file.getCanonicalPath().startsWith(prefix)||relative.startsWith("/")||relative.contains("\\"))throw new IOException("INVALID_SPEECH_RESOURCE_PATH");return file;
    }
    public String voices() throws Exception {
        JSONArray providers=new JSONArray(),voices=new JSONArray();String issue=null;
        try{prepare();}catch(Throwable e){issue=failure;}
        boolean available=prepared;
        int piperReady=0,espeakReady=0;JSONArray modelErrors=new JSONArray();
        if(available){
            JSONArray entries=manifest.getJSONArray("voices");
            for(int i=0;i<entries.length();i++){
                JSONObject entry=new JSONObject(entries.getJSONObject(i).toString());boolean ready=true;String reason=null;
                try{prepareVoice(entry.getString("id"));piperReady++;}catch(Exception error){ready=false;reason=error.getMessage();modelErrors.put(new JSONObject().put("voice",entry.getString("id")).put("error",reason));}
                entry.put("provider","piper").put("installed",ready).put("runtime_available",!ready||nativeFailure!=null?false:nativeLoaded?true:JSONObject.NULL).put("runtime_tested",testedVoices.contains("piper/"+entry.getString("id"))).put("native_initialized",nativeLoaded).put("error",reason==null?JSONObject.NULL:reason).put("managed",false).put("removable",false).put("bundled",true).put("network_required",false);voices.put(entry);
            }
            String[][] fallback={{"ro","Română","ro-RO"},{"en-us","English","en-US"},{"de","Deutsch","de-DE"}};
            for(String[] entry:fallback){String dictionary=entry[0].equals("en-us")?"en":entry[0];boolean ready=safeFile("espeak-ng-data/"+dictionary+"_dict").isFile();if(ready)espeakReady++;voices.put(new JSONObject().put("id",entry[0]).put("provider","espeak-ng").put("name","eSpeak NG · "+entry[1]).put("language",entry[2]).put("quality","compact").put("installed",ready).put("runtime_available",!ready||nativeFailure!=null?false:nativeLoaded?true:JSONObject.NULL).put("runtime_tested",testedVoices.contains("espeak-ng/"+entry[0])).put("native_initialized",nativeLoaded).put("managed",false).put("removable",false).put("bundled",true).put("network_required",false).put("license","GPL-3.0-or-later"));}
        }
        providers.put(new JSONObject().put("id","piper").put("available",piperReady>0&&nativeFailure==null).put("native_initialized",nativeLoaded).put("offline",true).put("reason",nativeFailure!=null?nativeFailure:issue==null?JSONObject.NULL:issue).put("voice_errors",modelErrors));
        providers.put(new JSONObject().put("id","espeak-ng").put("available",espeakReady>0&&nativeFailure==null).put("native_initialized",nativeLoaded).put("offline",true).put("reason",nativeFailure!=null?nativeFailure:issue==null?JSONObject.NULL:issue));
        return new JSONObject().put("platform","android").put("providers",providers).put("voices",voices).put("offline",true).toString();
    }
    public String synthesize(String provider,String voice,String text,double speed,String outputPath) throws Exception{return synthesize(provider,voice,text,speed,outputPath,"speech");}
    public String synthesize(String provider,String voice,String text,double speed,String outputPath,String requestId,String expectedLanguage)throws Exception{
        prepare();String expected=speechLanguage(expectedLanguage);if(expected.isEmpty())throw new IOException("EXPECTED_LANGUAGE_REQUIRED");String actual="";
        if(provider.equals("piper")){JSONArray entries=manifest.getJSONArray("voices");for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);if(entry.getString("id").equals(voice))actual=speechLanguage(entry.getString("language"));}}
        else if(provider.equals("espeak-ng"))actual=speechLanguage(voice);
        if(!actual.equals(expected))throw new IOException("VOICE_LANGUAGE_MISMATCH");return synthesize(provider,voice,text,speed,outputPath,requestId);
    }
    private static String speechLanguage(String value){String code=value==null?"":value.replace('_','-').toLowerCase(java.util.Locale.ROOT).split("-")[0];return switch(code){case "ron","rum" -> "ro";case "eng" -> "en";case "deu","ger" -> "de";default -> code;};}
    public String synthesize(String provider,String voice,String text,double speed,String outputPath,String requestId) throws Exception{
        prepare();if(text==null||text.trim().isEmpty()||text.length()>25000)throw new IllegalArgumentException("INVALID_SPEECH_TEXT");
        if(!Double.isFinite(speed)||speed<0.5||speed>2.2)throw new IllegalArgumentException("INVALID_SPEECH_SPEED");
        String model="",config="";
        if(provider.equals("piper")){
            JSONObject selected=null;JSONArray entries=manifest.getJSONArray("voices");for(int i=0;i<entries.length();i++)if(entries.getJSONObject(i).getString("id").equals(voice))selected=entries.getJSONObject(i);
            if(selected==null)throw new IllegalArgumentException("VOICE_NOT_INSTALLED_OR_CORRUPT");
            prepareVoice(voice);
            model=safeFile("voices/"+voice+"/"+voice+".onnx").getAbsolutePath();config=model+".json";
        }else if(!provider.equals("espeak-ng")||!java.util.Arrays.asList("ro","en-us","de").contains(voice))throw new IllegalArgumentException("UNSUPPORTED_SPEECH_PROVIDER");
        File output=new File(outputPath);String fileRoot=context.getFilesDir().getCanonicalPath()+File.separator;String cacheRoot=context.getCacheDir().getCanonicalPath()+File.separator;
        if(!output.getCanonicalPath().startsWith(fileRoot)&&!output.getCanonicalPath().startsWith(cacheRoot))throw new IllegalArgumentException("INVALID_AUDIO_OUTPUT_PATH");
        File parent=output.getParentFile();if(!parent.isDirectory()&&!parent.mkdirs())throw new IOException("AUDIO_FILE_NOT_WRITABLE");
        loadNative();
        final long token;
        synchronized(requestLock){if(cancelledRequests.remove(requestId))throw new IllegalStateException("CANCELLED");if(!activeRequest.compareAndSet(null,requestId))throw new IllegalStateException("SPEECH_BUSY");token=nativeBegin();}
        long began=System.nanoTime();
        try{
            JSONObject result=new JSONObject(nativeSynthesize(provider,voice,model,config,safeFile("espeak-ng-data").getAbsolutePath(),text.getBytes(StandardCharsets.UTF_8),speed,output.getAbsolutePath(),token));
            result.put("path",output.getAbsolutePath()).put("sha256",sha256(output)).put("bytes",output.length()).put("provider",provider).put("voice",voice).put("offline",true).put("request_id",requestId).put("elapsed_ms",(System.nanoTime()-began)/1_000_000);
            testedVoices.add(provider+"/"+voice);
            return result.toString();
        }catch(Throwable e){output.delete();if(provider.equals("piper")&&!"CANCELLED".equals(e.getMessage()))synchronized(this){preparedVoices.remove(voice);}throw e;}finally{activeRequest.compareAndSet(requestId,null);}
    }
    public void cancel(){synchronized(requestLock){if(nativeLoaded)nativeCancel();}}
    public void shutdown(){if(nativeLoaded)nativeShutdown();preparedVoices.clear();testedVoices.clear();}
    private static String sha256(File file) throws Exception{
        MessageDigest hash=MessageDigest.getInstance("SHA-256");try(InputStream in=new BufferedInputStream(new FileInputStream(file))){byte[] buffer=new byte[1024*1024];int n;while((n=in.read(buffer))!=-1)hash.update(buffer,0,n);}
        StringBuilder result=new StringBuilder();for(byte b:hash.digest())result.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return result.toString();
    }
    private static native long nativeBegin();
    private static native void nativeCancel();
    private static native boolean nativeCanVoice(String data,String voice);
    private static native String nativeSynthesize(String provider,String voice,String model,String config,String data,byte[] text,double speed,String output,long token);
    private static native void nativeShutdown();
}
