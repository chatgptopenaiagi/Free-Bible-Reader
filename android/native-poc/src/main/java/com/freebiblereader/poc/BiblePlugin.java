package com.freebiblereader.poc;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.util.Log;
import com.getcapacitor.*;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.*;
import java.io.*;
@CapacitorPlugin(name="Bible") public class BiblePlugin extends Plugin {
 @PluginMethod public void test(PluginCall call) {
  try {
   long start=System.nanoTime(); JSONArray results=new JSONArray();
   String[][] editions={{"reader.sqlite","web","love"},{"romanian.sqlite","ronbl","dragoste"}};
   for(String[] edition:editions) {
    File dest=new File(getContext().getFilesDir(),edition[0]);
    if(!dest.exists()) try(InputStream in=getContext().getAssets().open("fbr/data/"+edition[0]);OutputStream out=new FileOutputStream(dest)){byte[] buffer=new byte[262144];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);}
    try(SQLiteDatabase db=SQLiteDatabase.openDatabase(dest.toString(),null,SQLiteDatabase.OPEN_READONLY)){
     JSONArray verses=new JSONArray();
     try(Cursor c=db.rawQuery("SELECT verse,text FROM Verse WHERE edition=? AND book=? AND chapter=? ORDER BY rowid",new String[]{edition[1],"John","3"})){while(c.moveToNext())verses.put(new JSONArray().put(c.getString(0)).put(c.getString(1)));}
     long hits; try(Cursor c=db.rawQuery("SELECT count(*) FROM Verse WHERE edition=? AND text LIKE ?",new String[]{edition[1],"%"+edition[2]+"%"})){c.moveToFirst();hits=c.getLong(0);}
     results.put(new JSONObject().put("edition",edition[1]).put("chapter_count",verses.length()).put("sample",verses.optJSONArray(15)).put("search_count",hits));
    }
   }
   JSObject result=new JSObject();result.put("status","PASS");result.put("engine","capacitor-native-sqlite");result.put("results",results);result.put("elapsed_ms",(System.nanoTime()-start)/1000000.0);
   Log.i("FBR_POC",result.toString());call.resolve(result);
  }catch(Exception ex){Log.e("FBR_POC","FAIL",ex);call.reject(ex.toString());}
 }
}
