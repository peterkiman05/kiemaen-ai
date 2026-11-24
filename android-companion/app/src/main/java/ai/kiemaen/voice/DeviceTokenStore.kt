package ai.kiemaen.voice

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Stores the paired-device bearer token encrypted with a non-exportable Android Keystore key. */
object DeviceTokenStore {
    private const val PREFS = "kiemaen_device_secure"
    private const val KEY_ALIAS = "kiemaen_device_token_v1"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }

    fun save(activity: android.content.Context, token: String, commandToken: String, deviceId: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal("$token\n$commandToken".toByteArray(Charsets.UTF_8))
        activity.getSharedPreferences(PREFS, 0).edit()
            .putString("token", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("device_id", deviceId)
            .apply()
    }

    private fun credentials(activity: android.content.Context): List<String>? {
        val prefs = activity.getSharedPreferences(PREFS, 0)
        val encrypted = prefs.getString("token", null) ?: return null
        val iv = prefs.getString("iv", null) ?: return null
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                key(),
                GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP))
            )
            String(cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP)), Charsets.UTF_8)
                .split("\\n")
                .takeIf { it.size == 2 && it.all(String::isNotBlank) }
        } catch (_: Exception) {
            clear(activity)
            null
        }
    }

    fun token(activity: android.content.Context): String? = credentials(activity)?.get(0)

    fun commandToken(activity: android.content.Context): String? = credentials(activity)?.get(1)

    fun deviceId(activity: android.content.Context): String? =
        activity.getSharedPreferences(PREFS, 0).getString("device_id", null)

    fun clear(activity: android.content.Context) {
        activity.getSharedPreferences(PREFS, 0).edit().clear().apply()
        try {
            KeyStore.getInstance("AndroidKeyStore").apply { load(null) }.deleteEntry(KEY_ALIAS)
        } catch (_: Exception) {}
    }
}
