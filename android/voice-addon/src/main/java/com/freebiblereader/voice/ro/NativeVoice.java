package com.freebiblereader.voice.ro;

final class NativeVoice {
    static { System.loadLibrary("fbr_ro_voice"); }
    static native long begin();
    static native void cancel();
    static native boolean validate(String dataPath);
    static native long synthesize(String dataPath, byte[] utf8, int rate, int pitch, Object sink, long token);
    private NativeVoice() {}
}
