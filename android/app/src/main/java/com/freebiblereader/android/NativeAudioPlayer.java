package com.freebiblereader.android;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** One app-private WAV player, independent of WebView codec/autoplay behavior. */
final class NativeAudioPlayer {
    private static final Handler MAIN=new Handler(Looper.getMainLooper());
    private static Context context;
    private static MediaPlayer player;
    private static AudioManager manager;
    private static AudioFocusRequest focus;
    private static boolean prepared,playRequested,completed,resumeOnGain,focusHeld;
    private static String state="idle",error;
    private static long id;
    private static float volume=1;
    private interface Action {JSONObject run() throws Exception;}
    static void initialize(Context owner){context=owner.getApplicationContext();manager=(AudioManager)context.getSystemService(Context.AUDIO_SERVICE);}
    static JSONObject invoke(String operation,JSONObject payload)throws Exception{
        return onMain(()->switch(operation){
            case "playback.start" -> start(payload);
            case "playback.pause" -> pause();
            case "playback.resume" -> resume(payload);
            case "playback.stop" -> stop();
            case "playback.volume" -> setVolume(payload);
            case "playback.status" -> snapshot();
            default -> throw new IOException("UNSUPPORTED_PLAYBACK_OPERATION");
        });
    }
    private static JSONObject onMain(Action action)throws Exception{
        if(Looper.myLooper()==Looper.getMainLooper())return action.run();
        CountDownLatch done=new CountDownLatch(1);JSONObject[] value={null};Exception[] failure={null};
        MAIN.post(()->{try{value[0]=action.run();}catch(Exception e){failure[0]=e;}finally{done.countDown();}});
        if(!done.await(5,TimeUnit.SECONDS))throw new IOException("PLAYBACK_CONTROL_TIMEOUT");if(failure[0]!=null)throw failure[0];return value[0];
    }
    private static File source(JSONObject request)throws Exception{
        if(context==null)throw new IOException("PLAYBACK_NOT_INITIALIZED");File file=new File(request.getString("source")).getCanonicalFile();String path=file.getPath();
        if(!path.startsWith(context.getFilesDir().getCanonicalPath()+File.separator)&&!path.startsWith(context.getCacheDir().getCanonicalPath()+File.separator))throw new IOException("INVALID_AUDIO_SOURCE");
        if(!file.isFile()||file.length()<44||file.length()>256L*1024*1024)throw new IOException("INVALID_AUDIO_SOURCE");
        try(FileInputStream input=new FileInputStream(file)){byte[] header=new byte[12];if(input.read(header)!=12||header[0]!='R'||header[1]!='I'||header[2]!='F'||header[3]!='F'||header[8]!='W'||header[9]!='A'||header[10]!='V'||header[11]!='E')throw new IOException("INVALID_WAV_SOURCE");}
        return file;
    }
    private static float volume(JSONObject request)throws Exception{double value=request.optDouble("volume",volume);if(!Double.isFinite(value)||value<0||value>1)throw new IOException("INVALID_PLAYBACK_VOLUME");return(float)value;}
    private static JSONObject start(JSONObject request)throws Exception{
        File source=source(request);float desiredVolume=volume(request);release();id++;final long token=id;volume=desiredVolume;completed=false;error=null;prepared=false;playRequested=true;resumeOnGain=false;state="preparing";
        MediaPlayer created=new MediaPlayer();player=created;
        created.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
        created.setVolume(volume,volume);
        created.setOnPreparedListener(ready->{if(player!=ready||token!=id)return;prepared=true;if(playRequested)beginPlaying();else state="paused";});
        created.setOnCompletionListener(done->{if(player!=done||token!=id)return;completed=true;playRequested=false;resumeOnGain=false;state="completed";abandonFocus();});
        created.setOnErrorListener((failed,what,extra)->{if(player==failed&&token==id)fail("MEDIA_ERROR_"+what+"_"+extra);return true;});
        try{created.setDataSource(source.getAbsolutePath());created.prepareAsync();}catch(Exception failure){fail("AUDIO_PREPARATION_FAILED");throw new IOException("AUDIO_PREPARATION_FAILED",failure);}
        return snapshot();
    }
    private static boolean requestFocus(){
        if(focusHeld)return true;if(manager==null)return false;
        AudioAttributes attributes=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
        focus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attributes).setAcceptsDelayedFocusGain(false).setOnAudioFocusChangeListener(change->{
            if(change==AudioManager.AUDIOFOCUS_LOSS){resumeOnGain=false;playRequested=false;pauseCurrent();abandonFocus();}
            else if(change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT||change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK){resumeOnGain=state.equals("playing");pauseCurrent();}
            else if(change==AudioManager.AUDIOFOCUS_GAIN&&resumeOnGain){resumeOnGain=false;if(playRequested)beginPlaying();}
        },MAIN).build();
        focusHeld=manager.requestAudioFocus(focus)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED;return focusHeld;
    }
    private static void beginPlaying(){if(player==null||!prepared)return;if(!requestFocus()){fail("AUDIO_FOCUS_DENIED");return;}try{player.start();state="playing";}catch(Exception failure){fail("AUDIO_START_FAILED");}}
    private static void pauseCurrent(){if(player!=null&&prepared)try{if(player.isPlaying())player.pause();state="paused";}catch(Exception failure){fail("AUDIO_PAUSE_FAILED");}}
    private static JSONObject pause()throws Exception{playRequested=false;resumeOnGain=false;pauseCurrent();if(player!=null&&!prepared)state="paused";return snapshot();}
    private static JSONObject resume(JSONObject request)throws Exception{
        volume=volume(request);if(player==null||completed)throw new IOException("NO_ACTIVE_AUDIO");player.setVolume(volume,volume);playRequested=true;resumeOnGain=false;if(prepared)beginPlaying();else state="preparing";return snapshot();
    }
    private static JSONObject stop()throws Exception{playRequested=false;resumeOnGain=false;completed=false;release();state="stopped";error=null;return snapshot();}
    private static JSONObject setVolume(JSONObject request)throws Exception{volume=volume(request);if(player!=null)player.setVolume(volume,volume);return snapshot();}
    private static void fail(String code){error=code;state="error";completed=false;playRequested=false;resumeOnGain=false;release();}
    private static void abandonFocus(){if(manager!=null&&focus!=null)try{manager.abandonAudioFocusRequest(focus);}catch(Exception ignored){}focus=null;focusHeld=false;}
    private static void release(){MediaPlayer old=player;player=null;prepared=false;if(old!=null)try{old.setOnPreparedListener(null);old.setOnCompletionListener(null);old.setOnErrorListener(null);old.release();}catch(Exception ignored){}abandonFocus();}
    private static JSONObject snapshot()throws Exception{
        int position=0,duration=0;if(player!=null&&prepared)try{position=player.getCurrentPosition();duration=player.getDuration();}catch(Exception failure){fail("AUDIO_STATUS_FAILED");}
        return new JSONObject().put("state",state).put("playback_id",id).put("position_ms",position).put("duration_ms",duration).put("completed",completed).put("error",error==null?JSONObject.NULL:error).put("volume",volume).put("native_playback",true);
    }
    static void shutdown(){Runnable cleanup=()->{release();completed=false;playRequested=false;state="idle";context=null;manager=null;};if(Looper.myLooper()==Looper.getMainLooper())cleanup.run();else MAIN.post(cleanup);}
}
