package com.freebiblereader.android;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Text exports using Android PDF and the documented, editable OpenXML format.
 * Requests have already passed studio.documents' bounds and provenance checks.
 * The bridge never interprets Scripture, markup or source URLs as instructions.
 */
public final class AndroidDocuments {
    private record Paragraph(String text, boolean heading) {}
    private static List<Paragraph> paragraphs(JSONObject request) throws Exception {
        List<Paragraph> result = new ArrayList<>();
        result.add(new Paragraph(request.getString("title"), true));
        JSONObject settings = request.getJSONObject("settings");
        addBlocks(result, request.getJSONArray("blocks"), settings, false);
        if (settings.getBoolean("include_notes")) addBlocks(result, request.getJSONArray("notes"), settings, true);
        return result;
    }
    private static void addBlocks(List<Paragraph> result, JSONArray blocks, JSONObject s, boolean note) throws Exception {
        for (int i=0;i<blocks.length();i++) {
            JSONObject block=blocks.getJSONObject(i);
            String label=s.getBoolean("include_references")?block.optString("reference",""):"";
            String source=s.getBoolean("include_source_labels")?block.optString("label",""):"";
            if (!source.isEmpty()) label += (label.isEmpty()?"":" · ")+source;
            if (note) label="Personal note"+(label.isEmpty()?"":" · "+label);
            if (block.optString("kind").equals("correction")) label="Personal corrected copy"+(label.isEmpty()?"":" · "+label);
            if (!label.isEmpty()) result.add(new Paragraph(label,true));
            result.add(new Paragraph(block.getString("text"),false));
        }
    }
    public static JSONObject generate(JSONObject envelope) throws Exception {
        JSONObject request=envelope.getJSONObject("request");
        String format=envelope.getString("format");
        File output=new File(envelope.getString("output_path"));
        if (!format.equals(request.getString("format")) || !(format.equals("pdf")||format.equals("docx"))) throw new IllegalArgumentException("Unsupported document format");
        if (output.exists()) throw new IllegalArgumentException("Export staging file already exists");
        try {
            int pages=format.equals("pdf")?pdf(request,output):docx(request,output);
            return new JSONObject().put("format",format).put("bytes",output.length()).put("pages",pages)
                .put("selectable_text",true).put("editable",format.equals("docx"))
                .put("rendered_font",request.getJSONObject("settings").getString("font_family"));
        } catch (Exception error) { output.delete();throw error; }
    }
    private static Typeface face(JSONObject s, boolean heading) throws Exception {
        String family=s.getString("font_family");
        return Typeface.create(family.equals("serif")?"serif":family.equals("mono")?"monospace":"sans-serif",heading?Typeface.BOLD:Typeface.NORMAL);
    }
    private static int pdf(JSONObject request, File output) throws Exception {
        JSONObject s=request.getJSONObject("settings"), margins=s.getJSONObject("margins_mm");
        boolean letter=s.getString("paper").equals("Letter");
        int width=letter?612:595,height=letter?792:842;
        float left=(float)(margins.getDouble("left")*72/25.4),right=(float)(margins.getDouble("right")*72/25.4);
        float top=(float)(margins.getDouble("top")*72/25.4),bottom=(float)(margins.getDouble("bottom")*72/25.4);
        float textSize=(float)s.getDouble("font_size"), line=textSize*1.5f, usable=width-left-right;
        PdfDocument document=new PdfDocument();PdfDocument.Page page=null;Canvas canvas=null;
        Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);paint.setColor(Color.BLACK);
        int number=0;float y=height;
        try {
            for (Paragraph paragraph:paragraphs(request)) {
                paint.setTypeface(face(s,paragraph.heading));paint.setTextSize(paragraph.heading?textSize*1.15f:textSize);
                List<String> lines=new ArrayList<>();
                for (String raw:paragraph.text.split("\n",-1)) {
                    if (raw.isEmpty()) { lines.add("");continue; }
                    int offset=0;
                    while (offset<raw.length()) {
                        int count=paint.breakText(raw,offset,raw.length(),true,usable,null);
                        if(count<1) count=Character.charCount(raw.codePointAt(offset));
                        if(offset+count<raw.length() && count>1) {
                            int space=raw.lastIndexOf(' ',offset+count-1);
                            if(space>offset) count=space-offset+1;
                        }
                        // Avoid splitting a Unicode surrogate pair at a wrapped edge.
                        if(offset+count<raw.length() && Character.isHighSurrogate(raw.charAt(offset+count-1)))count--;
                        if(count<1)count=Character.charCount(raw.codePointAt(offset));
                        lines.add(raw.substring(offset,offset+count));offset+=count;
                    }
                }
                for (String text:lines) {
                    if (page==null || y+line>height-bottom-16) {
                        if(page!=null)document.finishPage(page);
                        page=document.startPage(new PdfDocument.PageInfo.Builder(width,height,++number).create());canvas=page.getCanvas();
                        Paint furniture=new Paint(Paint.ANTI_ALIAS_FLAG);furniture.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));furniture.setTextSize(8);furniture.setColor(Color.DKGRAY);
                        canvas.drawText(s.getString("header"),left,Math.max(12,top-18),furniture);
                        String footer=s.getString("footer");canvas.drawText(footer,left,height-bottom+18,furniture);
                        if(s.getBoolean("page_numbers")){String p=Integer.toString(number);canvas.drawText(p,width-right-furniture.measureText(p),height-bottom+18,furniture);}
                        y=top+textSize;
                    }
                    String align=s.getString("alignment");float x=left;
                    if(align.equals("right"))x=width-right-paint.measureText(text);
                    if(align.equals("center"))x=left+(usable-paint.measureText(text))/2;
                    // PDF justification retains the exact source string and adjusts
                    // word spacing only. The last wrapped line remains left aligned.
                    if(align.equals("justify") && !text.equals(lines.get(lines.size()-1))) {
                        int spaces=(int)text.chars().filter(c->c==' ').count();
                        if(spaces>0)paint.setWordSpacing(Math.max(0,(usable-paint.measureText(text))/spaces));
                    }
                    canvas.drawText(text,x,y,paint);paint.setWordSpacing(0);y+=line;
                }
                y+=textSize*.55f;
            }
            if(page!=null){document.finishPage(page);page=null;}
            try(FileOutputStream stream=new FileOutputStream(output)){document.writeTo(stream);}
        } finally { if(page!=null)try{document.finishPage(page);}catch(Exception ignored){}document.close(); }
        return number;
    }
    private static String xml(String value) {
        return value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;").replace("'","&apos;");
    }
    private static void entry(ZipOutputStream zip,String name,String value) throws Exception {
        zip.putNextEntry(new ZipEntry(name));zip.write(value.getBytes(StandardCharsets.UTF_8));zip.closeEntry();
    }
    private static String run(String value) {
        StringBuilder out=new StringBuilder("<w:r>");
        String[] lines=value.split("\n",-1);
        for(int i=0;i<lines.length;i++){if(i>0)out.append("<w:br/>");out.append("<w:t xml:space=\"preserve\">").append(xml(lines[i])).append("</w:t>");}
        return out.append("</w:r>").toString();
    }
    private static int docx(JSONObject request, File output) throws Exception {
        JSONObject s=request.getJSONObject("settings"),m=s.getJSONObject("margins_mm");
        String ns=" xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"";
        String prefix="<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>";
        String font=s.getString("font_family").equals("serif")?"Noto Serif":s.getString("font_family").equals("mono")?"Noto Sans Mono":"Noto Sans";
        int size=(int)Math.round(s.getDouble("font_size")*2);
        StringBuilder body=new StringBuilder(prefix+"<w:document"+ns+"><w:body>");
        for(Paragraph p:paragraphs(request)) {
            body.append("<w:p><w:pPr>");
            if(p.heading)body.append("<w:pStyle w:val=\"Heading2\"/><w:keepNext/>");
            else body.append("<w:jc w:val=\"").append(s.getString("alignment").equals("justify")?"both":s.getString("alignment")).append("\"/>");
            body.append("<w:spacing w:after=\"160\" w:line=\"300\" w:lineRule=\"auto\"/></w:pPr>").append(run(p.text)).append("</w:p>");
        }
        boolean letter=s.getString("paper").equals("Letter");
        body.append("<w:sectPr><w:headerReference w:type=\"default\" r:id=\"header\"/><w:footerReference w:type=\"default\" r:id=\"footer\"/><w:pgSz w:w=\"").append(letter?12240:11906).append("\" w:h=\"").append(letter?15840:16838).append("\"/><w:pgMar");
        for(String edge:new String[]{"top","right","bottom","left"})body.append(" w:").append(edge).append("=\"").append(Math.round(m.getDouble(edge)*1440/25.4)).append("\"");
        body.append(" w:header=\"400\" w:footer=\"400\"/></w:sectPr></w:body></w:document>");
        String styles=prefix+"<w:styles"+ns+"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii=\""+font+"\" w:hAnsi=\""+font+"\" w:cs=\""+font+"\"/><w:sz w:val=\""+size+"\"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\"><w:name w:val=\"Normal\"/></w:style><w:style w:type=\"paragraph\" w:styleId=\"Heading2\"><w:name w:val=\"heading 2\"/><w:basedOn w:val=\"Normal\"/><w:rPr><w:b/></w:rPr></w:style></w:styles>";
        String relStart=prefix+"<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">";
        String relType="http://schemas.openxmlformats.org/officeDocument/2006/relationships/";
        String contentTypes=prefix+"<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/>";
        for(String[] spec:new String[][]{{"document","document.main"},{"styles","styles"},{"header1","header"},{"footer1","footer"}})contentTypes+="<Override PartName=\"/word/"+spec[0]+".xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml."+spec[1]+"+xml\"/>";
        contentTypes+="</Types>";
        String footer=prefix+"<w:ftr"+ns+"><w:p>"+run(s.getString("footer"));
        if(s.getBoolean("page_numbers"))footer+="<w:r><w:tab/></w:r><w:fldSimple w:instr=\"PAGE\"><w:r><w:t>1</w:t></w:r></w:fldSimple>";
        footer+="</w:p></w:ftr>";
        try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(output))) {
            entry(zip,"[Content_Types].xml",contentTypes);
            entry(zip,"_rels/.rels",relStart+"<Relationship Id=\"doc\" Type=\""+relType+"officeDocument\" Target=\"word/document.xml\"/></Relationships>");
            entry(zip,"word/document.xml",body.toString());entry(zip,"word/styles.xml",styles);
            entry(zip,"word/_rels/document.xml.rels",relStart+"<Relationship Id=\"styles\" Type=\""+relType+"styles\" Target=\"styles.xml\"/><Relationship Id=\"header\" Type=\""+relType+"header\" Target=\"header1.xml\"/><Relationship Id=\"footer\" Type=\""+relType+"footer\" Target=\"footer1.xml\"/></Relationships>");
            entry(zip,"word/header1.xml",prefix+"<w:hdr"+ns+"><w:p>"+run(s.getString("header"))+"</w:p></w:hdr>");entry(zip,"word/footer1.xml",footer);
        }
        return 0; // DOCX pagination is determined by the user's document editor.
    }
}
