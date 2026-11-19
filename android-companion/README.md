# Kiemaen Voice for Android

A native Android companion for the Kiemaen AI service.

- Local wake-word detection using Sherpa-ONNX; no Picovoice account, AccessKey, or paid wake-word service.
- Built-in wake phrase: **Hey Kiemaen**.
- Wake-word model and runtime are packaged into the debug APK by the build workflow.
- After activation, Android SpeechRecognizer transcribes one request; recognised text is sent to Kiemaen over HTTPS.
- Android TextToSpeech reads the reply aloud and the wake-word detector restarts after the reply.
- Optional in-app Kiemaen account linking lets the companion reuse the site's HttpOnly session cookie. Without linking, guest chat remains available.

## Build

Requires JDK 17, Android SDK 35, and Python 3.11.

    cd android-companion
    bash ./prepare-deps.sh
    gradle --no-daemon :app:assembleDebug

The preparation script downloads the official Sherpa-ONNX 2.0.2 Android AAR and the English GigaSpeech keyword-spotting model, verifies the AAR checksum, and generates the custom Hey Kiemaen keyword tokens. These downloaded binaries and model files are intentionally not committed to this repository. GitHub Actions runs the same preparation step and publishes a debug APK artifact named kiemaen-voice-debug-apk.

## First-time phone setup

1. Install the APK on the Android phone.
2. Open Kiemaen Voice and choose Connect Kiemaen Account if you want signed-in tasks and account-scoped access. Complete the normal Kiemaen website login and email-code verification inside the in-app browser, then tap Done.
3. Grant microphone and notification permissions.
4. Tap Start Hey Kiemaen Listening while the app is open.
5. Wait for the notification to say it is listening locally.
6. Say Hey Kiemaen, pause briefly, then speak your request.
7. Kiemaen's reply is spoken aloud. Say the wake phrase again for another request.
8. Use Stop in the app or the persistent notification to stop microphone access.

## Privacy and platform limits

Wake-word matching is performed locally on the phone. The app does not upload continuous microphone audio. After the wake phrase, Android's configured speech-recognition provider receives the active utterance for transcription; the recognised text is then sent to Kiemaen over HTTPS. The local wake detector does not require internet after installation, but the Kiemaen response requires internet.

Android and Huawei battery-management policies can stop background microphone services. Start listening from the visible app, keep its foreground notification, and allow background activity/battery use for Kiemaen Voice if you want it to remain available with the screen off. No Android app can promise uninterrupted microphone access if the operating system force-stops it.

The companion currently uses Kiemaen's /chat endpoint. The app can pass the site's signed-in session cookie when linked; the backend does not yet provide persistent conversational memory across independent requests, so account linking should not be mistaken for long-term chat memory.
