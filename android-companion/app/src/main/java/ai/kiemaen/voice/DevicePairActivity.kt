package ai.kiemaen.voice

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.webkit.CookieManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.Executors

class DevicePairActivity : Activity() {
    private lateinit var status: TextView
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 36, 28, 28)
        }
        root.addView(TextView(this).apply {
            text = "SECURE DEVICE PAIRING"
            textSize = 23f
        })
        root.addView(TextView(this).apply {
            text = "Pairing links this phone to your signed-in Kiemaen account. Secure command access is stored encrypted with Android Keystore. Kiemaen can directly set alarms and open installed apps when you request them. Other phone actions remain unavailable."
            textSize = 14f
            setPadding(0, 14, 0, 20)
        })
        status = TextView(this).apply { textSize = 14f; text = "Checking pairing status…" }
        root.addView(status)
        root.addView(Button(this).apply {
            text = "PAIR THIS PHONE"
            setOnClickListener {
                AlertDialog.Builder(this@DevicePairActivity)
                    .setTitle("Pair this phone with Kiemaen?")
                    .setMessage("This registers this phone and enables direct delivery of supported commands: set alarms and open installed apps. It does not grant access to messages, calls, files, payments, settings, or arbitrary phone control.")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Pair") { _, _ -> pair() }
                    .show()
            }
        })
        root.addView(Button(this).apply {
            text = "CHECK CONNECTION"
            setOnClickListener { heartbeat() }
        })
        root.addView(Button(this).apply {
            text = "UNPAIR THIS PHONE"
            setOnClickListener { unpair() }
        })
        setContentView(root)
        showLocalState()
    }

    private fun showLocalState() {
        val id = DeviceTokenStore.deviceId(this)
        status.text = if (id == null) {
            "This phone is not paired. Sign in using Connect Kiemaen Account first."
        } else if (DeviceTokenStore.commandToken(this) == null) {
            "This phone has an older heartbeat-only pairing. Tap PAIR THIS PHONE again to enable direct alarms and app launching."
        } else {
            "Paired device ID: $id\nDirect alarm and app-launch commands are enabled. Use Check Connection to verify the secure link."
        }
    }

    private fun pair() {
        val cookies = CookieManager.getInstance().getCookie(AccountActivity.BASE_URL).orEmpty()
        if (!cookies.contains("session_token=")) {
            status.text = "Please connect and sign in to your Kiemaen account first."
            return
        }
        status.text = "Pairing securely…"
        executor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = URL("${AccountActivity.BASE_URL}/device/pair").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 15000
                connection.readTimeout = 20000
                connection.doOutput = true
                connection.setRequestProperty("Cookie", cookies)
                connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                val body = "device_name=" + URLEncoder.encode(android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL, "UTF-8")
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val json = JSONObject(stream?.bufferedReader()?.use { it.readText() }.orEmpty())
                if (code !in 200..299 || json.optString("status") != "ok") {
                    throw IllegalStateException(json.optString("detail", "Pairing failed. Sign in again and retry."))
                }
                DeviceTokenStore.save(this, json.getString("device_token"), json.getString("command_token"), json.getString("device_id"))
                runOnUiThread {
                    status.text = "Phone paired. Direct alarms and app-launch commands are enabled. Keep Kiemaen's listening service running to receive website commands."
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "Pairing failed: ${e.message ?: "connection error"}" }
            } finally {
                connection?.disconnect()
            }
        }
    }

    private fun heartbeat() {
        val token = DeviceTokenStore.token(this)
        if (token == null) {
            status.text = "This phone is not paired."
            return
        }
        status.text = "Checking secure connection…"
        executor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = URL("${AccountActivity.BASE_URL}/device/heartbeat").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 12000
                connection.readTimeout = 15000
                connection.setRequestProperty("Authorization", "Bearer $token")
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val json = JSONObject(stream?.bufferedReader()?.use { it.readText() }.orEmpty())
                if (code !in 200..299) throw IllegalStateException(json.optString("detail", "Device token rejected."))
                runOnUiThread {
                    status.text = "Connected securely. Device: ${json.optString("device_name")}\nCapabilities: alarms and opening installed apps. Commands enabled: ${json.optBoolean("commands_enabled")}"
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "Connection check failed: ${e.message ?: "network error"}" }
            } finally {
                connection?.disconnect()
            }
        }
    }

    private fun unpair() {
        val id = DeviceTokenStore.deviceId(this)
        if (id == null) {
            status.text = "This phone is already unpaired."
            return
        }
        val cookies = CookieManager.getInstance().getCookie(AccountActivity.BASE_URL).orEmpty()
        if (!cookies.contains("session_token=")) {
            status.text = "Sign in to Kiemaen to revoke this device, then try again."
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Unpair this phone?")
            .setMessage("Kiemaen will revoke this device token. You can pair it again later.")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Unpair") { _, _ ->
                status.text = "Revoking device access…"
                executor.execute {
                    var connection: HttpURLConnection? = null
                    try {
                        connection = URL("${AccountActivity.BASE_URL}/device/revoke").openConnection() as HttpURLConnection
                        connection.requestMethod = "POST"
                        connection.connectTimeout = 12000
                        connection.readTimeout = 15000
                        connection.doOutput = true
                        connection.setRequestProperty("Cookie", cookies)
                        connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                        connection.outputStream.use {
                            it.write(("device_id=" + URLEncoder.encode(id, "UTF-8")).toByteArray(Charsets.UTF_8))
                        }
                        val code = connection.responseCode
                        if (code !in 200..299) throw IllegalStateException("Server did not revoke this device (HTTP $code).")
                        DeviceTokenStore.clear(this)
                        runOnUiThread { status.text = "Phone unpaired. Its device token has been revoked." }
                    } catch (e: Exception) {
                        runOnUiThread { status.text = "Unpair failed: ${e.message ?: "network error"}" }
                    } finally {
                        connection?.disconnect()
                    }
                }
            }
            .show()
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
