# Kiemaen Voice for Android

Separate Android companion for the Kiemaen AI service. Wake-word detection runs locally using Picovoice Porcupine. After activation, Android SpeechRecognizer transcribes one utterance, recognized text is sent to Kiemaen over HTTPS, and Android TextToSpeech speaks the reply.

## Build
Open this folder in Android Studio, or run gradle :app:assembleDebug with JDK 17 and Android SDK 35. The APK is at app/build/outputs/apk/debug/app-debug.apk. GitHub Actions also builds and publishes a debug APK artifact.

## First-time setup
1. Install the APK on Android.
2. Create a Picovoice account at https://console.picovoice.ai/ and copy your AccessKey.
3. Enter the AccessKey in Kiemaen Voice and save it locally.
4. For an initial smoke test, start listening for the built-in Computer wake phrase.
5. For Hey Kiemaen, create an Android .ppn custom wake-word model in Picovoice Console, download it, and import it in the app. The private model file is not stored in Git.
6. Grant microphone and notification permissions. Start listening while the app is visible. The ongoing notification provides a stop control.
7. On Huawei devices, allow auto-launch, background activity and background battery use in device settings.

## Platform and privacy limits
- Android requires microphone foreground services to be started while the app is visible and microphone permission is granted. Start listening manually after reboot; the app does not silently restart microphone capture on boot.
- Huawei battery management may still stop long-running services. A persistent notification indicates the service state but cannot guarantee 24/7 operation.
- Wake-word matching is local. After activation, Android SpeechRecognizer uses the configured recognition service and may send speech to that provider. Recognized text is sent to the public Kiemaen chat guest endpoint over HTTPS. Do not speak passwords, payment details or other secrets.
- The companion currently uses guest chat. Authenticated account context and persistent personal conversation memory are not connected yet.
- The Picovoice AccessKey is stored in app-private preferences. Android app backup is disabled.
- This is an initial integration; test on the target Huawei phone before relying on it.

## Safety
The app sends recognized text to the existing chat endpoint. It does not execute shell commands, set alarms, send messages or perform other device actions.
