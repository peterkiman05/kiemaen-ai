package ai.kiemaen.voice

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.Toast

class AccountActivity : Activity() {
    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CookieManager.getInstance().setAcceptCookie(true)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        root.addView(Button(this).apply {
            text = "DONE — RETURN TO KIEMAEN VOICE"
            setOnClickListener {
                CookieManager.getInstance().flush()
                val cookie = CookieManager.getInstance().getCookie(BASE_URL).orEmpty()
                val linked = cookie.split(";").any { it.trim().startsWith("session_token=") }
                Toast.makeText(
                    this@AccountActivity,
                    if (linked) "Kiemaen account linked." else "No signed-in session found. Complete login first.",
                    Toast.LENGTH_LONG
                ).show()
                finish()
            }
        })

        webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return false
                if (uri.host == HOST) return false
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                    true
                } catch (_: Exception) {
                    true
                }
            }
        }
        root.addView(webView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1f
        ))
        setContentView(root)
        webView.loadUrl(BASE_URL)
    }

    override fun onDestroy() {
        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }

    companion object {
        const val BASE_URL = "https://kiemaen-ai.onrender.com"
        private const val HOST = "kiemaen-ai.onrender.com"
    }
}
