package com.freebiblereader.poc;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;
public class MainActivity extends BridgeActivity {
 @Override public void onCreate(Bundle b) { registerPlugin(BiblePlugin.class); super.onCreate(b); }
}
