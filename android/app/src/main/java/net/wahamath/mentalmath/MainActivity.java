package net.wahamath.mentalmath;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.speech.tts.TextToSpeech;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;

import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * غلاف التطبيق: يعرض app/index.html من أصول الحزمة على أصل https ثابت (WebViewAssetLoader)، فتعمل وحدات JavaScript
 * و fetch، وتبقى IndexedDB في الأصل نفسه بين التشغيلات. نطق المتصفح لا يعمل في WebView، فالنطق من TextToSpeech
 * عبر AndroidTTS. والنسخة الاحتياطية تُكتب في مجلد التنزيلات عبر AndroidFiles، واستيرادها باختيار ملف.
 */
public class MainActivity extends Activity {
    private static final int PICK = 1;
    private WebView web;
    private TextToSpeech tts;
    private volatile boolean ttsReady = false;
    private ValueCallback<Uri[]> picked;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        if (BuildConfig.MM_INSPECT) WebView.setWebContentsDebuggingEnabled(true);   // بناء الاختبار وحده
        tts = new TextToSpeech(this, status -> ttsReady = status == TextToSpeech.SUCCESS);
        web = new WebView(this);
        setContentView(web);
        immersive();

        // نوع الملف صريحًا: وحدات JavaScript تُرفض إن خُدمت بنوع غير JavaScript، و .mjs قد لا يعرفه المحمّل
        WebViewAssetLoader.AssetsPathHandler assets = new WebViewAssetLoader.AssetsPathHandler(this);
        WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", path -> {
                    WebResourceResponse r = assets.handle(path);
                    if (r == null) return null;
                    String type = path.endsWith(".mjs") || path.endsWith(".js") ? "text/javascript"
                            : path.endsWith(".json") ? "application/json"
                            : path.endsWith(".css") ? "text/css"
                            : path.endsWith(".html") ? "text/html"
                            : path.endsWith(".webmanifest") ? "application/manifest+json" : r.getMimeType();
                    return new WebResourceResponse(type, "utf-8", r.getData());
                })
                .build();
        web.setWebViewClient(new WebViewClientCompat() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (picked != null) picked.onReceiveValue(null);
                picked = callback;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                startActivityForResult(Intent.createChooser(i, null), PICK);
                return true;
            }
        });
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        web.addJavascriptInterface(new Speech(), "AndroidTTS");
        web.addJavascriptInterface(new Files(), "AndroidFiles");
        web.loadUrl("https://appassets.androidplatform.net/assets/app/index.html");
    }

    private void immersive() {
        web.setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }

    @Override
    public void onWindowFocusChanged(boolean focus) {
        super.onWindowFocusChanged(focus);
        if (focus) immersive();
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != PICK || picked == null) return;
        Uri u = result == RESULT_OK && data != null ? data.getData() : null;
        picked.onReceiveValue(u == null ? null : new Uri[]{u});
        picked = null;
    }

    @Override
    public void onBackPressed() {
        // زر الرجوع لا يُخرج الطفل من التطبيق بلمسة خاطئة: الخروج من الشاشة الرئيسية للجهاز
    }

    @Override
    protected void onDestroy() {
        if (tts != null) tts.shutdown();
        super.onDestroy();
    }

    /** النطق: has(lang) هل للغة صوت مثبت؟ و speak(text, lang). */
    class Speech {
        @JavascriptInterface
        public boolean ready() { return ttsReady; }

        @JavascriptInterface
        public boolean has(String lang) {
            if (!ttsReady) return false;
            return tts.isLanguageAvailable(new Locale(lang)) >= TextToSpeech.LANG_AVAILABLE;
        }

        @JavascriptInterface
        public void speak(String text, String lang) {
            if (!ttsReady) return;
            tts.setLanguage(new Locale(lang));
            tts.setSpeechRate(0.9f);
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "mm");
        }
    }

    /** النسخة الاحتياطية: save(name, text) يكتب الملف في مجلد التنزيلات، ويعيد مكانه أو نص الخطأ مسبوقًا بـ «!». */
    class Files {
        @JavascriptInterface
        public String save(String name, String text) {
            byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
            try {
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Downloads.DISPLAY_NAME, name);
                    v.put(MediaStore.Downloads.MIME_TYPE, "application/json");
                    v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                    Uri u = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    if (u == null) return "!تعذّر إنشاء الملف";
                    try (OutputStream o = getContentResolver().openOutputStream(u)) { o.write(bytes); }
                    return "Download/" + name;
                }
                File dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                dir.mkdirs();
                File f = new File(dir, name);
                try (FileOutputStream o = new FileOutputStream(f)) { o.write(bytes); }
                return f.getAbsolutePath();
            } catch (Exception e) {
                return "!" + e;
            }
        }
    }
}
