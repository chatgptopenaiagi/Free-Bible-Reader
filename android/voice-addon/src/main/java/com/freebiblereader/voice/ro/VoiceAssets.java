package com.freebiblereader.voice.ro;

import android.content.Context;
import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;

final class VoiceAssets {
    static synchronized File ensure(Context context) throws Exception {
        File root=new File(context.getFilesDir(),"romanian-engine");root.mkdirs();
        JSONObject manifest;
        try(InputStream in=context.getAssets().open("espeak-ro/manifest.json")){
            ByteArrayOutputStream text=new ByteArrayOutputStream();byte[] bytes=new byte[8192];int n;
            while((n=in.read(bytes))!=-1){if(text.size()+n>100000)throw new IOException("Manifest bound exceeded");text.write(bytes,0,n);}
            manifest=new JSONObject(text.toString("UTF-8"));
        }
        JSONArray files=manifest.getJSONArray("files");if(files.length()>24)throw new IOException("Unexpected resource count");
        for(int i=0;i<files.length();i++){
            JSONObject entry=files.getJSONObject(i);String name=entry.getString("path");long size=entry.getLong("bytes");
            File target=new File(root,name);if(!target.getCanonicalPath().startsWith(root.getCanonicalPath()+File.separator))throw new SecurityException("Unsafe voice data path");
            if(size<0||size>2000000)throw new IOException("Voice data size bound");
            if(target.isFile()&&target.length()==size&&hash(target).equals(entry.getString("sha256")))continue;
            target.getParentFile().mkdirs();File partial=new File(target+".part");long total=0;
            try(InputStream in=context.getAssets().open("espeak-ro/"+name);OutputStream out=new FileOutputStream(partial)){
                byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1){total+=n;if(total>size)throw new IOException("Voice data exceeds manifest");out.write(bytes,0,n);}
            }
            if(total!=size||!hash(partial).equals(entry.getString("sha256"))){partial.delete();throw new IOException("Voice integrity mismatch");}
            Files.move(partial.toPath(),target.toPath(),StandardCopyOption.REPLACE_EXISTING);
        }
        return new File(root,"espeak-ng-data");
    }
    static String hash(File file)throws Exception{
        MessageDigest md=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] data=new byte[65536];int n;while((n=in.read(data))!=-1)md.update(data,0,n);}
        StringBuilder text=new StringBuilder();for(byte b:md.digest())text.append(String.format("%02x",b));return text.toString();
    }
}
