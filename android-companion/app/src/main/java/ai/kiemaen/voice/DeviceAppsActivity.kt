package ai.kiemaen.voice

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class DeviceAppsActivity : Activity() {
    private lateinit var list: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 32, 28, 24)
        }
        root.addView(TextView(this).apply {
            text = "DEVICE APPS"
            textSize = 24f
        })
        root.addView(TextView(this).apply {
            text = "Apps are discovered locally on this phone. Tap an app to open it immediately. The installed-app list stays on your device."
            textSize = 14f
            setPadding(0, 12, 0, 20)
        })
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(list)
        setContentView(root)
        loadApps()
    }

    @Suppress("DEPRECATION")
    private fun loadApps() {
        list.removeAllViews()
        val launcherIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = packageManager.queryIntentActivities(launcherIntent, 0)
            .distinctBy { it.activityInfo.packageName }
            .sortedBy { it.loadLabel(packageManager).toString().lowercase() }

        if (apps.isEmpty()) {
            list.addView(TextView(this).apply { text = "No launchable apps were found." })
            return
        }

        apps.forEach { info ->
            val label = info.loadLabel(packageManager).toString()
            val row = TextView(this).apply {
                text = "  $label"
                textSize = 17f
                gravity = Gravity.CENTER_VERTICAL
                minHeight = 56
                setPadding(12, 8, 12, 8)
                setOnClickListener { openApp(label, info.activityInfo.packageName) }
            }
            list.addView(row)
        }
    }

    private fun openApp(label: String, packageName: String) {
        val launch = packageManager.getLaunchIntentForPackage(packageName)
        if (launch == null) {
            Toast.makeText(this, "This app cannot be opened from its launcher entry.", Toast.LENGTH_SHORT).show()
            return
        }
        try {
            startActivity(launch)
        } catch (_: Exception) {
            Toast.makeText(this, "Android could not open $label.", Toast.LENGTH_SHORT).show()
        }
    }
}
