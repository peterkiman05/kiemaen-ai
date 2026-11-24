# Kiemaen AI for Android

The Android launcher icon, splash screen and home screen use the Kiemaen five-leaf clover mark and dark navy/blue brand palette.

A native Android companion for the Kiemaen AI service.

## Current capabilities

- Local **Hey Kiemaen** wake-word detection using Sherpa-ONNX; no paid wake-word account or API key.
- Wake-word model and runtime are packaged into the Android build by CI.
- After activation, Android SpeechRecognizer transcribes the request and sends recognised text to Kiemaen over HTTPS.
- Android TextToSpeech reads replies aloud and the wake-word detector restarts after the reply.
- Optional Kiemaen account linking reuses the site's signed-in session cookie.
- Local launcher-app discovery uses Android launcher activities. The app list stays on the phone.
- Tapping an app in the local app list launches it directly.
- Secure pairing issues separate heartbeat and command tokens. The raw tokens are encrypted together at rest with an Android Keystore AES-GCM key; the server stores only token hashes.
- While the foreground listening service is running, it polls the authenticated command queue and can execute these supported actions without a second per-command approval:
  - **Set an alarm** through Android's `AlarmClock.ACTION_SET_ALARM` with `EXTRA_SKIP_UI=true`.
  - **Open an installed app** by matching the requested app name to an Android launcher activity.
- Command requests are account/device scoped, limited to an explicit action allowlist, expire quickly, are claimed once, and report success/failure.
- Revoking a paired device disables both tokens and cancels its queued commands.

## Important boundaries

Pairing is the one-time opt-in that enables the two supported remote actions. Routine requests for alarms and app launches do not show another approval prompt.

This is not unrestricted phone control. It cannot read notifications or messages, capture the screen, send messages, make calls, make purchases/payments, change security settings, delete files, execute shell commands, or automate taps inside other apps. Unsupported requests must be handled conversationally rather than being translated into arbitrary Android intents or code.

The phone must be paired to the same signed-in Kiemaen account. Keep **Start Hey Kiemaen Listening** active for the foreground service to poll commands from the website. Polling is approximately every 10 seconds. If the service is stopped, the phone is offline, or Android/Huawei battery controls stop the service, website commands will wait only until their short expiry and then be discarded.

Android may restrict launching an activity while the app is backgrounded, depending on OS version, OEM policy and app state. The command handler reports failures; actual background execution needs on-device testing on the target phone.

Existing devices paired before command tokens were introduced must be paired again once in the updated app. This rotates in fresh heartbeat and command credentials. Revoking the old device entry from **/devices** is recommended after successful re-pairing.

## Build outputs

The GitHub Actions workflow builds:

- **Debug APK** for direct sideload testing.
- **Android App Bundle (AAB)** as a Google Play packaging preview.

The AAB is not yet release-signed with a Play upload key and is not published to Google Play. Store signing, listing, policy declarations and review are separate steps. No signing key or store credential is committed to this repository.

## First-time phone setup

1. Install the APK on the Android phone.
2. Open Kiemaen Voice and choose **Connect Kiemaen Account**.
3. Sign in to the same Kiemaen account used on the website.
4. Open **Secure Device Pairing** and tap **PAIR THIS PHONE** once.
5. Grant microphone and notification permissions.
6. Tap **Start Hey Kiemaen Listening** and keep its foreground notification active for hands-free voice and website-to-phone commands.
7. From the website or voice assistant, try **“open WhatsApp”** or **“set an alarm for 6:30 am”**.
8. To stop microphone access and command polling, use Stop in the app or persistent notification. Revoking the device on **/devices** disables its tokens server-side.

## Privacy

Wake-word matching is performed locally. Continuous microphone audio is not uploaded. After the wake phrase, Android's configured speech-recognition provider receives the active utterance for transcription; recognised text is then sent to Kiemaen over HTTPS.

Installed-app discovery stays on-device and uses launcher intent visibility; the app does not request the sensitive `QUERY_ALL_PACKAGES` permission. Device tokens are encrypted using Android Keystore and command payloads are constrained by server-side validation.

## Build locally

Requires JDK 17, Android SDK 35 and Python 3.11.

    cd android-companion
    bash ./prepare-deps.sh
    gradle --no-daemon :app:assembleDebug
    gradle --no-daemon :app:bundleRelease

The preparation script downloads the official Sherpa-ONNX Android AAR and English keyword-spotting model, verifies the AAR checksum, and generates the custom wake-word keyword tokens. Downloaded binaries and model files are intentionally not committed.
