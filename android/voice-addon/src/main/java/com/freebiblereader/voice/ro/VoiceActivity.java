package com.freebiblereader.voice.ro;

import android.app.Activity;
import android.content.*;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.os.*;
import android.provider.Settings;
import android.speech.tts.*;
import android.text.InputFilter;
import android.view.View;
import android.widget.*;
import java.util.*;

/** Native diagnostics and explicit preview. Never writes the system TTS default. */
public final class VoiceActivity extends Activity {
    public static final String SAMPLE="Bună ziua! Aceasta este o voce română offline. Țară, școală, început, credință și iubire.";
    private TextToSpeech speech;
    private TextView status,voiceInfo,speedLabel;
    private EditText sample;
    private Spinner engines;
    private SeekBar speed;
    private Button play;
    private final List<String> enginePackages=new ArrayList<>();
    private String currentEngine;
    private long session;
    private Voice romanian;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private boolean destroyed;

    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().setNavigationBarColor(Color.rgb(24,78,86));
        ScrollView scroll=new ScrollView(this);LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(22),dp(28),dp(22),dp(28));body.setBackgroundColor(Color.rgb(247,246,239));scroll.addView(body);setContentView(scroll);
        TextView title=text("Romanian Offline Voice",27);title.setTextColor(Color.rgb(24,78,86));body.addView(title);
        body.addView(text("O voce română disponibilă fără internet",17));
        body.addView(text("Basic eSpeak NG voice · small offline engine\nThis companion contains no Bible database or neural model. It can be selected by Free Bible Reader and other Android TTS clients.",15));
        body.addView(text("Speech engine",17));engines=new Spinner(this);engines.setContentDescription("Installed speech engine");body.addView(engines,wide());
        voiceInfo=text("Checking installed engines…",15);body.addView(voiceInfo);
        sample=new EditText(this);sample.setText(SAMPLE);sample.setMinLines(3);sample.setTextSize(19);sample.setFilters(new InputFilter[]{new InputFilter.LengthFilter(4000)});sample.setContentDescription("Romanian pronunciation test text");body.addView(sample,wide());
        speedLabel=text("Speed 1.00×",16);body.addView(speedLabel);speed=new SeekBar(this);speed.setMin(50);speed.setMax(200);speed.setProgress(100);speed.setContentDescription("Speech speed");body.addView(speed,wide());
        speed.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){}public void onStopTrackingTouch(SeekBar b){}public void onProgressChanged(SeekBar b,int p,boolean user){speedLabel.setText(String.format(Locale.ROOT,"Speed %.2f×",p/100f));}});
        play=button("▶ Test Romanian",body,()->preview());play.setEnabled(false);button("■ Stop",body,()->{if(speech!=null)speech.stop();status.setText("Playback stopped.");});
        button("Refresh installed engines",body,this::discover);
        button("Open Android voice settings",body,()->{try{startActivity(new Intent("com.android.settings.TTS_SETTINGS"));}catch(ActivityNotFoundException error){try{startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));}catch(ActivityNotFoundException ignored){status.setText("Open Settings → Accessibility → Text-to-speech on this device.");}}});
        status=text("Preparing the Romanian engine…",16);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);body.addView(status);
        body.addView(text("The system default is never changed automatically. This is a basic formant voice, separate from Piper Mihai. Pronunciation and speaker quality can vary by device.\n\nVersion "+BuildConfig.VERSION_NAME+" · eSpeak NG GPL-3.0-or-later\nSource and notices are included with the release.",14));
        discover();
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private LinearLayout.LayoutParams wide(){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(8);p.bottomMargin=dp(8);return p;}
    private TextView text(String value,int size){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(Color.rgb(29,42,46));v.setPadding(0,dp(8),0,dp(8));return v;}
    private Button button(String title,LinearLayout parent,Runnable action){Button b=new Button(this);b.setText(title);b.setMinHeight(dp(48));b.setOnClickListener(v->action.run());parent.addView(b,wide());return b;}
    private void discover(){
        List<ResolveInfo> found=getPackageManager().queryIntentServices(new Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE),0);
        found.sort((a,b)->{boolean x=a.serviceInfo.packageName.equals(getPackageName()),y=b.serviceInfo.packageName.equals(getPackageName());return x==y?a.serviceInfo.packageName.compareTo(b.serviceInfo.packageName):(x?-1:1);});
        List<String> labels=new ArrayList<>();enginePackages.clear();
        for(ResolveInfo info:found){String pack=info.serviceInfo.packageName;if(!info.serviceInfo.exported||enginePackages.contains(pack))continue;enginePackages.add(pack);labels.add(info.loadLabel(getPackageManager())+"\n"+pack);}
        if(enginePackages.isEmpty()){voiceInfo.setText("No speech engine is visible. Reopen the app after installation.");play.setEnabled(false);return;}
        engines.setOnItemSelectedListener(null);ArrayAdapter<String> list=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,labels);list.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);engines.setAdapter(list);
        engines.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onNothingSelected(AdapterView<?> p){}public void onItemSelected(AdapterView<?> p,View v,int index,long id){connect(enginePackages.get(index));}});
        engines.setSelection(0);currentEngine=null;connect(enginePackages.get(0));
    }
    private void connect(String pack){
        if(pack.equals(currentEngine)&&speech!=null)return;
        currentEngine=pack;romanian=null;play.setEnabled(false);long token=++session;
        if(speech!=null){speech.stop();speech.shutdown();speech=null;}
        status.setText("Connecting to selected engine…");
        speech=new TextToSpeech(this,code->ui.post(()->{
            if(destroyed||token!=session)return;
            if(code!=TextToSpeech.SUCCESS){voiceInfo.setText("The selected engine could not start. No fallback voice will be spoken.");status.setText("Engine unavailable.");return;}
            try{
                Set<Voice> reported=speech.getVoices();List<Voice> candidates=new ArrayList<>();
                if(reported!=null)for(Voice v:reported)if("ro".equalsIgnoreCase(v.getLocale().getLanguage()))candidates.add(v);
                candidates.sort(Comparator.comparing(Voice::isNetworkConnectionRequired).thenComparing(Voice::getName));
                if(pack.equals(getPackageName()))candidates.removeIf(v->!RomanianTtsService.VOICE.equals(v.getName()));
                if(candidates.isEmpty()){voiceInfo.setText("No Romanian voice is reported by this engine. Install its Romanian language data in Android settings, or select this companion.");status.setText("Romanian unavailable; no English fallback.");return;}
                romanian=candidates.get(0);voiceInfo.setText("Romanian: "+romanian.getName()+"\nLocale: "+romanian.getLocale().toLanguageTag()+" · "+(romanian.isNetworkConnectionRequired()?"Network required":"Offline voice"));
                play.setEnabled(true);status.setText("Ready. Tap Test Romanian to hear the selected voice.");
                speech.setOnUtteranceProgressListener(new UtteranceProgressListener(){public void onStart(String id){ui.post(()->status.setText("Reading the Romanian test…"));}public void onDone(String id){ui.post(()->status.setText("Test finished. You can replay or choose another installed engine."));}public void onError(String id){ui.post(()->status.setText("The selected voice could not finish. No different voice was substituted."));}});
            }catch(Throwable error){voiceInfo.setText("Voice discovery failed: "+error.getClass().getSimpleName());}
        }),pack);
    }
    private void preview(){
        if(speech==null||romanian==null)return;
        if(speech.setVoice(romanian)!=TextToSpeech.SUCCESS||speech.getVoice()==null||!romanian.getName().equals(speech.getVoice().getName())||!"ro".equals(speech.getVoice().getLocale().getLanguage())){status.setText("The engine did not accept that exact Romanian voice. Playback was not started.");return;}
        speech.setSpeechRate(speed.getProgress()/100f);
        if(speech.speak(sample.getText().toString(),TextToSpeech.QUEUE_FLUSH,new Bundle(),"romanian-preview")!=TextToSpeech.SUCCESS)status.setText("The engine rejected the request. Try a shorter sentence.");
    }
    @Override protected void onDestroy(){destroyed=true;++session;if(speech!=null){speech.stop();speech.shutdown();speech=null;}super.onDestroy();}
}
