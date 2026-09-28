import subprocess
import requests
import re
import os
import time
import speech_recognition as sr

RENDER_URL = "https://kiemaen-ai.onrender.com/chat"

def speak(text):
    print(f"\nJARVIS: {text}")
    subprocess.run(["termux-tts-speak", text])

def handle_hardware(text):
    alarm_match = re.search(r'\[ALARM:(\d{2}:\d{2})\]', text)
    if alarm_match:
        time_str = alarm_match.group(1)
        subprocess.run(["termux-alarm-set", "-t", time_str, "-m", "AI Assistant"])
        text = text.replace(alarm_match.group(0), "")
        print(f"⚙️ Action: Alarm set for {time_str}")
    return text.strip()

def record_and_convert(duration=4):
    raw_file = "raw_voice.wav"
    clean_file = "clean_voice.wav"
    
    # Cleanup old files
    for f in [raw_file, clean_file]:
        if os.path.exists(f): os.remove(f)

    print("\n🎤 Listening... (Speak now)")
    # Record raw audio
    subprocess.run(["termux-microphone-record", "-f", raw_file, "-l", str(duration)])
    time.sleep(duration + 0.5)
    subprocess.run(["termux-microphone-record", "-q"]) # Safely stop recording

    if not os.path.exists(raw_file):
        return None

    print("⚡ Converting audio format...")
    # Convert raw audio into standard PCM WAV using ffmpeg
    conversion = subprocess.run([
        "ffmpeg", "-y", "-i", raw_file, 
        "-ar", "16000", "-ac", "1", clean_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Cleanup raw file
    if os.path.exists(raw_file): os.remove(raw_file)

    if conversion.returncode != 0 or not os.path.exists(clean_file):
        print("x Audio conversion failed")
        return None

    return clean_file

def transcribe_audio(filename):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(filename) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
    except sr.UnknownValueError:
        print("x Could not understand audio (try speaking closer)")
        return None
    except Exception as e:
        print(f"x Transcription error: {e}")
        return None

def run_assistant():
    speak("System online. Huawei background listener ready.")
    
    while True:
        audio_path = record_and_convert(duration=4)
        if not audio_path:
            continue

        print("⚡ Transcribing voice...")
        user_text = transcribe_audio(audio_path)
        
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if not user_text:
            continue
            
        print(f"YOU: {user_text}")
        print("🚀 Sending to Render Brain...")
        
        try:
            response = requests.post(RENDER_URL, data={"message": user_text}, timeout=15)
            
            if response.status_code == 200:
                try: 
                    ai_reply = response.json().get("response", "")
                except: 
                    ai_reply = response.text
                    
                final_speech = handle_hardware(ai_reply)
                if final_speech:
                    speak(final_speech)
            else:
                speak("Main server returned an error.")
        except Exception as e:
            print(f"x Network Error: {e}")

if __name__ == "__main__":
    run_assistant()
