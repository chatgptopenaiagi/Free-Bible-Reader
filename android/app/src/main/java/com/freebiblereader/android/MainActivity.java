package com.freebiblereader.android;

import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.os.*;
import android.net.Uri;
import android.util.Log;
import android.webkit.*;
import android.widget.*;
import com.chaquo.python.*;
import com.chaquo.python.android.AndroidPlatform;
import org.json.*;
import java.io.*;
import java.security.*;
import java.util.concurrent.*;

/** Android host only: portable research lives in the shared Python core. */
public class MainActivity extends Activity {
    private WebView web;
    private final ExecutorService startup=Executors.newSingleThreadExecutor();
    private String origin;
    private String sessionToken;
    public File bundleRoot;
    private boolean destroyed;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setNavigationBarColor(Color.rgb(24,40,45));
        TextView loading=new TextView(this);loading.setPadding(30,70,30,30);loading.setText("Free Bible Reader\nPreparing verified offline resources…");loading.setTextSize(22);setContentView(loading);
        PlatformAdapter.initialize(this);
        byte[] secret=new byte[32];new SecureRandom().nextBytes(secret);sessionToken=hex(secret);
        startup.submit(()->{
            try {
                if(BuildConfig.DEBUG&&getIntent().hasExtra("native_operation")){runNativeTest(getIntent());return;}
                // Keep verified immutable public resources across speech-only updates.
                // Personal libraries live separately in files/studio and are untouched.
                File legacy=new File(getFilesDir(),"bundle/0.3.0-"+BuildConfig.PRODUCT_VARIANT);
                bundleRoot=legacy.isDirectory()?legacy:new File(getFilesDir(),"bundle/"+BuildConfig.PRODUCT_VARIANT);
                extractResources(bundleRoot);
                if(!Python.isStarted())Python.start(new AndroidPlatform(this));
                Python py=Python.getInstance();
                py.getModule("sys").get("path").callAttr("insert",0,bundleRoot.toString());
                if(BuildConfig.DEBUG&&getIntent().getBooleanExtra("poc",false)) {
                    String result=py.getModule("poc").callAttr("run",bundleRoot.toString()).toString();
                    Log.i("FBR_POC",result);
                    runOnUiThread(()->{TextView report=new TextView(this);report.setPadding(24,40,24,24);report.setText(result);report.setTextIsSelectable(true);setContentView(report);});return;
                }
                int port=py.getModule("free_bible_reader.android_runtime").callAttr("start",bundleRoot.toString(),new File(getFilesDir(),"studio").toString(),BuildConfig.PRODUCT_VARIANT,sessionToken).toInt();
                origin="http://127.0.0.1:"+port;
                runOnUiThread(this::openReader);
            }catch(Throwable e){Log.e("FBR_ANDROID","Startup failed",e);runOnUiThread(()->{loading.setText("Unable to start Free Bible Reader.\n"+e.getClass().getSimpleName()+": "+e.getMessage());});}
        });
    }
    private void extractResources(File root)throws Exception {
        root.mkdirs();
        JSONObject manifest;
        try(InputStream in=getAssets().open("fbr/resource-manifest.json")){ByteArrayOutputStream text=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(text.size()+n>5000000)throw new IOException("Manifest bound exceeded");text.write(buffer,0,n);}manifest=new JSONObject(text.toString("UTF-8"));}
        JSONArray files=manifest.getJSONArray("files");
        for(int i=0;i<files.length();i++) {
            JSONObject record=files.getJSONObject(i);String relative=record.getString("path");
            File dest=new File(root,relative);if(!dest.getCanonicalPath().startsWith(root.getCanonicalPath()+File.separator))throw new SecurityException("Unsafe bundle path");
            long size=record.getLong("size");String hash=record.getString("sha256");
            File receipt=new File(root,".verified/"+hash);
            if(dest.isFile()&&dest.length()==size&&receipt.exists())continue;
            dest.getParentFile().mkdirs();File partial=new File(dest+".part");MessageDigest digest=MessageDigest.getInstance("SHA-256");
            try(InputStream in=getAssets().open("fbr/"+relative);OutputStream out=new FileOutputStream(partial)){
                byte[] buffer=new byte[262144];int n;while((n=in.read(buffer))!=-1){out.write(buffer,0,n);digest.update(buffer,0,n);}
            }
            if(partial.length()!=size||!hex(digest.digest()).equalsIgnoreCase(hash)){partial.delete();throw new IOException("Resource integrity mismatch: "+relative);}
            if(!partial.renameTo(dest))throw new IOException("Cannot install bundled resource: "+relative);
            receipt.getParentFile().mkdirs();try(OutputStream out=new FileOutputStream(receipt)){out.write(1);}
        }
    }
    private void openReader() {
        if(destroyed)return;
        CookieManager cookies=CookieManager.getInstance();cookies.setAcceptCookie(true);
        web=new WebView(this);WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.getSettings().setJavaScriptEnabled(true);web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setMediaPlaybackRequiresUserGesture(false);
        web.getSettings().setAllowFileAccess(false);web.getSettings().setAllowContentAccess(false);
        web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new Object(){@JavascriptInterface public String invoke(String op,String payload){if(!op.equals("preferences.load")&&!op.equals("preferences.save")&&!op.equals("settings.voices")&&!op.equals("app.quit")&&!op.equals("app.info"))return "{\"status\":\"ERROR\",\"error\":\"NATIVE_OPERATION_NOT_EXPOSED_TO_WEB\"}";return PlatformAdapter.invoke(op,payload);}},"FBRNative");
        web.setWebChromeClient(new WebChromeClient(){@Override public boolean onConsoleMessage(ConsoleMessage m){if(BuildConfig.DEBUG)Log.i("FBR_WEB",m.messageLevel()+" "+m.message()+" "+m.lineNumber());return true;}});
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return route(request.getUrl());}
            private boolean route(Uri uri){if(uri.toString().startsWith(origin+"/"))return false;if("https".equals(uri.getScheme())||"http".equals(uri.getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception ignored){}return true;}
        });
        FrameLayout host=new FrameLayout(this);host.setBackgroundColor(Color.rgb(24,40,45));host.addView(web,new FrameLayout.LayoutParams(-1,-1));host.setOnApplyWindowInsetsListener((view,insets)->{FrameLayout.LayoutParams layout=(FrameLayout.LayoutParams)web.getLayoutParams();layout.setMargins(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());web.setLayoutParams(layout);return insets;});setContentView(host);host.requestApplyInsets();cookies.setCookie(origin,"fbr_session="+sessionToken+"; Path=/; HttpOnly; SameSite=Strict",accepted->{cookies.flush();web.loadUrl(origin+(BuildConfig.PRODUCT_VARIANT.equals("lite")?"/lite/":"/"));});Log.i("FBR_ANDROID","Reader started "+BuildConfig.PRODUCT_VARIANT+" on private loopback");
    }
    public WebView getReaderWebView(){return web;}
    public String trustedOrigin(){return origin;}
    private void runNativeTest(Intent intent){String operation=intent.getStringExtra("native_operation"),payload=intent.getStringExtra("native_payload");if(intent.hasExtra("native_payload_b64"))payload=new String(android.util.Base64.decode(intent.getStringExtra("native_payload_b64"),android.util.Base64.DEFAULT),java.nio.charset.StandardCharsets.UTF_8);String testId=intent.getStringExtra("test_id");if(testId==null||!testId.matches("[A-Za-z0-9_-]{1,80}"))testId="result";String result=PlatformAdapter.invoke(operation,payload==null?"{}":payload);try{File folder=new File(getFilesDir(),"native-tests");folder.mkdirs();try(OutputStream out=new FileOutputStream(new File(folder,testId+".json"))){out.write(result.getBytes(java.nio.charset.StandardCharsets.UTF_8));}Log.i("FBR_NATIVE_TEST",operation+" completed");}catch(Exception error){Log.e("FBR_NATIVE_TEST","Cannot save test result",error);}final String display=result;runOnUiThread(()->{TextView report=new TextView(this);report.setText(display);report.setTextIsSelectable(true);setContentView(report);});}
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);if(BuildConfig.DEBUG&&intent.hasExtra("native_operation"))startup.submit(()->runNativeTest(intent));}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);PlatformAdapter.activityResult(request,result,data);}
    @Override public void onBackPressed(){if(web==null){super.onBackPressed();return;}web.evaluateJavascript("(()=>{const d=document.querySelector('dialog[open]');if(d){d.close();return true;}return false;})()",closed->{if("true".equals(closed))return;if(web.canGoBack())web.goBack();else finish();});}
    @Override protected void onDestroy(){destroyed=true;PlatformAdapter.shutdown();if(web!=null){web.removeJavascriptInterface("FBRNative");web.destroy();}if(Python.isStarted())new Thread(()->{try{Python.getInstance().getModule("free_bible_reader.android_runtime").callAttr("stop");}catch(Exception ignored){}} ,"fbr-stop").start();startup.shutdownNow();super.onDestroy();}
    static String hex(byte[] value){StringBuilder text=new StringBuilder();for(byte b:value)text.append(String.format("%02x",b));return text.toString();}
}
