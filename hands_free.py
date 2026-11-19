import subprocess
import requests
import re
import time

RENDER_URL = "https://kiemaen-ai.onrender.com/chat"

def speak(text):
    print(f"\nJARVIS: {text}")
    subprocess.run(["termux-tts-speak", text])

def handle_hardware(text):
    """Treat model output as untrusted; never execute device actions automatically."""
    cleaned = re.sub(r"\[ALARM:\d{2}:\d{2}\]", "[Alarm not set: explicit device confirmation is required.]", text)
    return block_untrusted_hardware_actions(cleaned)

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
