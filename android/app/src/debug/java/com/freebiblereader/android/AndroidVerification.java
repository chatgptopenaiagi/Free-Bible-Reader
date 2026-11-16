package com.freebiblereader.android;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import org.json.JSONObject;
import java.io.*;
/** Debug-only independent Android PDF rendering proof. */
public final class AndroidVerification {
 public static JSONObject renderPdf(JSONObject p)throws Exception {
  File source=new File(p.getString("source")),output=new File(p.getString("output_path"));
  try(ParcelFileDescriptor fd=ParcelFileDescriptor.open(source,ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer pdf=new PdfRenderer(fd);PdfRenderer.Page page=pdf.openPage(0)){
   Bitmap image=Bitmap.createBitmap(page.getWidth()*2,page.getHeight()*2,Bitmap.Config.ARGB_8888);image.eraseColor(Color.WHITE);page.render(image,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
   try(OutputStream out=new FileOutputStream(output)){if(!image.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("PNG encoding failed");}image.recycle();
   return new JSONObject().put("pages",pdf.getPageCount()).put("bytes",output.length()).put("path",output.toString());
  }
 }
}
