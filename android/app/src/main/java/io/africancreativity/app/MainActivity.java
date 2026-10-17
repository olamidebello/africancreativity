package io.africancreativity.app;

import android.app.Activity;
import android.Manifest;
import android.content.pm.PackageManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.ValueCallback;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Online creative studio client. Patient records remain on the creative studio service. */
public final class MainActivity extends Activity {
    private static final String HOME = "https://olamideolatayobello.com/";
    private WebView web;
    private LinearLayout root;
    private TextView notice;
    private Button retry;
    private PermissionRequest pendingAudio;
    private ValueCallback<Uri[]> pendingFiles;
    private static final int AUDIO_REQUEST = 21, FILE_REQUEST = 22;
    private boolean trusted(Uri uri) {
        return "https".equalsIgnoreCase(uri.getScheme()) && "olamideolatayobello.com".equalsIgnoreCase(uri.getHost())
                && (uri.getPort() == -1 || uri.getPort() == 443);
    }


    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        // Respect system bars when edge-to-edge is enforced on Android 15+.
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        notice = new TextView(this);
        notice.setPadding(24, 24, 24, 24);
        notice.setVisibility(View.GONE);
        retry = new Button(this);
        retry.setText("Retry creative studio connection");
        retry.setVisibility(View.GONE);
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setSaveFormData(false);
        settings.setSupportMultipleWindows(false);
        settings.setUserAgentString(settings.getUserAgentString() + " AfricaCreativityAndroid/1.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                boolean https = "https".equalsIgnoreCase(uri.getScheme());
                if (https && "olamideolatayobello.com".equalsIgnoreCase(uri.getHost())
                        && (uri.getPort() == -1 || uri.getPort() == 443)) return false;
                if (request.isForMainFrame() && request.hasGesture() && https) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                    catch (ActivityNotFoundException ignored) { showError(); }
                }
                return true;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showError();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                if (!trusted(request.getOrigin()) || request.getResources().length != 1
                        || !PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(request.getResources()[0])) { request.deny(); return; }
                if (pendingAudio != null) pendingAudio.deny();
                pendingAudio = request;
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE}); pendingAudio = null;
                } else requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, AUDIO_REQUEST);
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request) {
                if (pendingAudio == request) pendingAudio = null;
            }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (!trusted(Uri.parse(view.getUrl() == null ? "" : view.getUrl()))) return false;
                if (pendingFiles != null) pendingFiles.onReceiveValue(null);
                pendingFiles = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType("*/*");
                try { startActivityForResult(intent, FILE_REQUEST); }
                catch (ActivityNotFoundException ignored) { callback.onReceiveValue(null); pendingFiles = null; }
                return true;
            }
        });
        // No SSL-error override, native JavaScript bridge, offline projects or background tracking.
        retry.setOnClickListener(v -> {
            notice.setVisibility(View.GONE); retry.setVisibility(View.GONE);
            web.setVisibility(View.VISIBLE); web.loadUrl(HOME);
        });
        root.addView(notice); root.addView(retry);
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        web.loadUrl(HOME);
    }
    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == AUDIO_REQUEST && pendingAudio != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED
                    && trusted(pendingAudio.getOrigin()) && trusted(Uri.parse(web.getUrl() == null ? "" : web.getUrl())))
                pendingAudio.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            else pendingAudio.deny();
            pendingAudio = null;
        }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == FILE_REQUEST && pendingFiles != null) {
            Uri uri = result == RESULT_OK && data != null ? data.getData() : null;
            pendingFiles.onReceiveValue(uri == null ? null : new Uri[]{uri}); pendingFiles = null;
        }
    }
    private void showError() {
        web.setVisibility(View.GONE);
        notice.setText("Unable to connect securely to Africa Creativity. Check your internet connection and try again.");
        notice.setVisibility(View.VISIBLE); retry.setVisibility(View.VISIBLE);
    }
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onPause() { web.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override protected void onDestroy() { if (web != null) { root.removeView(web); web.destroy(); } super.onDestroy(); }
}
