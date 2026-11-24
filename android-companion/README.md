# Kiemaen AI for Android

The Android launcher icon, Android 12+ opening splash, and app home screen use the five-leaf Kiemaen clover mark with the dark navy and blue brand palette.

A native Android companion for the Kiemaen AI service. The current device-agent foundation is deliberately permission-first: **every app-opening action requires an on-screen confirmation**.

## Current capabilities

- Local wake-word detection using Sherpa-ONNX; no Picovoice account, AccessKey, or paid wake-word service.
- Built-in wake phrase: **Hey Kiemaen**.
- Wake-word model and runtime are packaged into the Android build by CI.
- After activation, Android SpeechRecognizer transcribes a request; recognised text is sent to Kiemaen over HTTPS.
- Android TextToSpeech reads the reply aloud and the wake-word detector restarts after the reply.
- Optional in-app Kiemaen account linking reuses the site's signed-in session cookie.
- Local launcher-app discovery shows apps Android exposes through the launcher intent. The list is not uploaded.
- Selecting an app opens a confirmation dialog; the app launches only after the user taps **Open**.
- User-confirmed device pairing to the signed-in Kiemaen account.
- Device bearer token encrypted at rest with an Android Keystore AES-GCM key.
- A narrowly scoped heartbeat endpoint and account-owned revocation. The token does not grant phone-control permissions.

## Build outputs

The GitHub Actions workflow builds two distribution artifacts:

- **Debug APK** for direct sideload testing.
- **Release Android App Bundle (AAB)** as a Google Play packaging preview.

The AAB is not yet signed with a release/upload key and is not published to Google Play. Play release signing, store listing, policy declarations and review are separate steps. No signing key or store credential is committed to this repository.

## Build locally

Requires JDK 17, Android SDK 35, and Python 3.11.

    cd android-companion
    bash ./prepare-deps.sh
    gradle --no-daemon :app:assembleDebug
    gradle --no-daemon :app:bundleRelease

The preparation script downloads the official Sherpa-ONNX 2.0.2 Android AAR and the English GigaSpeech keyword-spotting model, verifies the AAR checksum, and generates the custom Hey Kiemaen keyword tokens. Downloaded binaries and model files are intentionally not committed.

## First-time phone setup

1. Install the APK on the Android phone.
2. Open Kiemaen Voice and choose **Connect Kiemaen Account** if signed-in access is wanted.
3. Grant microphone and notification permissions.
4. Tap **Start Hey Kiemaen Listening** while the app is visible.
5. Say **Hey Kiemaen**, pause briefly, then speak your request.
6. Use **View and Open Device Apps** to inspect locally available launcher apps. Every app launch requires confirmation.
7. Use Stop in the app or persistent notification to stop microphone access.

## Privacy and platform limits

Wake-word matching is performed locally. Continuous microphone audio is not uploaded. After the wake phrase, Android's configured speech-recognition provider receives the active utterance for transcription; recognised text is then sent to Kiemaen over HTTPS.

App discovery is restricted to apps Android exposes as launcher activities. It stays on-device and does not request broad package visibility. This avoids requesting the sensitive `QUERY_ALL_PACKAGES` permission. It does not read app-private data, bypass app security, or automate taps inside other apps.

Android and Huawei battery-management policies can stop background microphone services. Start listening from the visible app, keep its foreground notification, and allow background activity/battery use for Kiemaen Voice if desired. Android may stop microphone access if the app is force-stopped.

## Device-agent rollout boundary

Secure enrollment and a heartbeat-only device token are implemented. Remote command delivery, notification reading, screen capture, and in-app workflows are **not enabled**. The paired token currently grants only device heartbeat/status access; it cannot open apps, read messages, or issue actions. Each additional capability requires a separate permission screen, a reviewed authenticated protocol, visible action previews, and explicit approval for every action. The selected autonomy setting is **confirm every phone action**; future features must preserve that rule.

No phone installation or on-device test has been performed as part of this repository change.
