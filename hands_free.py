import subprocess
import requests
import re
import time

RENDER_URL = "https://kiemaen-ai.onrender.com/chat"

def speak(text):
    print(f"\nJARVIS: {text}")
    subprocess.run(["termux-tts-speak", text])

def handle_hardware(text):
    # Intercept secret codes like [ALARM:07:00]
    alarm_match = re.search(r'\[ALARM:(\d{2}:\d{2})\]', text)
    if alarm_match:
        time_str = alarm_match.group(1)
        subprocess.run(["termux-alarm-set", "-t", time_str, "-m", "AI Assistant"])
        text = text.replace(alarm_match.group(0), "")
        print(f"⚙️ Action: Alarm set for {time_str}")
    return text.strip()

def run_assistant():
    speak("System online. I am ready.")
    
    while True:
        print("\n--- Listening (Speak now) ---")
        
        # Uses Android's native speech engine directly!
        user_text = subprocess.getoutput("termux-speech-to-text").strip()
        
        # If you didn't say anything or it didn't catch it, skip and listen again
        if not user_text or "error" in user_text.lower():
            time.sleep(1) 
            continue
            
        print(f"YOU: {user_text}")
        
        try:
            # Send to your live Render brain
            response = requests.post(RENDER_URL, data={"message": user_text})
            
            if response.status_code == 200:
                try: 
                    ai_reply = response.json().get("response", "")
                except: 
                    ai_reply = response.text
                    
                # Execute hardware commands, then speak the rest
                final_speech = handle_hardware(ai_reply)
                if final_speech:
                    speak(final_speech)
            else:
                speak("I lost connection to the brain.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_assistant()
