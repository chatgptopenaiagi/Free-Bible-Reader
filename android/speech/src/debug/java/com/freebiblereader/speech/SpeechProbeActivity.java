package com.freebiblereader.speech;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/** Debug-only, explicit real-runtime speech probe; no production exported endpoint. */
public final class SpeechProbeActivity extends Activity {
    @Override public void onCreate(Bundle state){
        super.onCreate(state);TextView status=new TextView(this);status.setText("Testing bundled Android speech…");setContentView(status);
        new Thread(()->{
            String name=getIntent().getStringExtra("probe_name");if(name==null||!name.matches("[A-Za-z0-9_-]{1,64}"))name="speech-probe";
            File directory=new File(getFilesDir(),"speech-probes");directory.mkdirs();
            String output;
            try{
                String provider=getIntent().getStringExtra("provider");
                if(provider==null)output=SpeechBridge.get(this).voices();
                else{
                    String voice=getIntent().getStringExtra("voice"),text=getIntent().getStringExtra("text");
                    JSONObject payload=new JSONObject().put("provider",provider).put("voice",voice).put("text",text).put("speed",getIntent().getDoubleExtra("speed",1.0)).put("output_path",new File(directory,name+".wav").getAbsolutePath()).put("request_id",name);
                    int cancelAfter=getIntent().getIntExtra("cancel_after_ms",0);
                    if(cancelAfter>0){final String request=name;new Thread(()->{try{Thread.sleep(Math.min(10000,cancelAfter));SpeechBridge.invoke(this,"speech.cancel",new JSONObject().put("request_id",request).toString());}catch(Exception ignored){}},"fbr-speech-cancellation-probe").start();}
                    output=SpeechBridge.invoke(this,"speech.synthesize",payload.toString());
                }
                try(FileOutputStream result=new FileOutputStream(new File(directory,name+".json"))){result.write(output.getBytes(StandardCharsets.UTF_8));}
            }catch(Throwable e){output="SPEECH_PROBE_FAILED: "+e.getClass().getSimpleName()+": "+e.getMessage();}
            final String message=output;runOnUiThread(()->status.setText(message));
        },"fbr-native-speech-probe").start();
    }
}
