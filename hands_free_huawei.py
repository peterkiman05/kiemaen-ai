import subprocess
import requests
import re
import os
import time
import shlex
import speech_recognition as sr

RENDER_URL = "https://kiemaen-ai.onrender.com"
CHAT_ENDPOINT = f"{RENDER_URL}/chat"
TELEMETRY_ENDPOINT = "http://127.0.0.1:8000/api/telemetry"

def speak(text):
    print(f"\nJARVIS: {text}")
    subprocess.run(["termux-tts-speak", text])

def execute_and_report_telemetry(command):
    print(f"⚙️ Executing Hardware Intent: {command}")
    try:
        args = shlex.split(command)
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        
        telemetry = {
            "command": command,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
        
        try:
            requests.post(TELEMETRY_ENDPOINT, json=telemetry, timeout=5)
        except Exception as net_err:
            print(f"⚠️ Telemetry reporting failed: {net_err}")
            
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        error_payload = {"command": command, "stdout": "", "stderr": str(e), "returncode": -1}
        try:
            requests.post(TELEMETRY_ENDPOINT, json=error_payload, timeout=5)
        except:
            pass
        return str(e)

def handle_hardware(text):
    exec_match = re.search(r'\[EXEC:(.*?)\]', text)
    if exec_match:
        command = exec_match.group(1).strip()
        execute_and_report_telemetry(command)
        text = text.replace(exec_match.group(0), "")
    return text.strip()

def record_and_convert(duration=4):
    raw_file = "raw_voice.wav"
    clean_file = "clean_voice.wav"
    
    for f in [raw_file, clean_file]:
        if os.path.exists(f): os.remove(f)

    print("\n🎤 Listening... (Speak now)")
    subprocess.run(["termux-microphone-record", "-f", raw_file, "-l", str(duration)])
    time.sleep(duration + 0.5)
    subprocess.run(["termux-microphone-record", "-q"])

    if not os.path.exists(raw_file): return None

    print("⚡ Converting audio format...")
    conversion = subprocess.run([
        "ffmpeg", "-y", "-i", raw_file, 
        "-ar", "16000", "-ac", "1", clean_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(raw_file): os.remove(raw_file)

    if conversion.returncode != 0 or not os.path.exists(clean_file):
        return None

    return clean_file

def transcribe_audio(filename):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(filename) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data)
    except:
        return None

def run_assistant():
    speak("Closed-Loop Telemetry Bridge online. Monitoring hardware execution.")
    
    while True:
        audio_path = record_and_convert(duration=4)
        if not audio_path: continue

        print("⚡ Transcribing voice...")
        user_text = transcribe_audio(audio_path)
        
        if os.path.exists(audio_path): os.remove(audio_path)
        if not user_text: continue
            
        print(f"YOU: {user_text}")
        
        tool_manual = (
            " [SYSTEM RULE: You have execution rights on Android via Termux. To perform tasks, append [EXEC: <command>] to your output. "
            "Alarm Example: [EXEC: am start -p com.google.android.deskclock -a android.intent.action.SET_ALARM --ei android.intent.extra.alarm.HOUR <HH> --ei android.intent.extra.alarm.MINUTES <MM> --ez android.intent.extra.alarm.SKIP_UI true] | "
            "Torch Example: [EXEC: termux-torch on]]"
        )
        
        payload = f"{user_text}{tool_manual}"
        form_data = {"prompt": payload, "msg": payload}
        
        try:
            response = requests.post(CHAT_ENDPOINT, data=form_data, timeout=60)
            if response.status_code == 200:
                try: ai_reply = response.json().get("response", "")
                except: ai_reply = response.text
                
                final_speech = handle_hardware(ai_reply)
                if final_speech: speak(final_speech)
            else:
                speak(f"Server error code {response.status_code}.")
        except Exception as e:
            print(f"x Network Error: {e}")

if __name__ == "__main__":
    run_assistant()
