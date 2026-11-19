import os
import subprocess

# Let's search all python files for where system messages or API calls happen
target_files = ["core/brain.py", "main.py", "agent.py", "core/agent.py"]
patched = False

for path in target_files:
    if not os.path.exists(path):
        continue
        
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
        
    # Check if we can find system prompt or role setup
    if "system" in code.lower() or "role" in code.lower() or "prompt" in code.lower():
        # Inject the hardware instruction directly into the code logic
        rule_code = '\n# System hardware rule injection\nSYSTEM_ALARM_INSTRUCTION = " You are an autonomous AI connected to an Android phone. If the user asks to set an alarm or wake up, you MUST include the tag [ALARM:HH:MM] in 24-hour format in your response (e.g. [ALARM:07:00])."\n'
        
        if "SYSTEM_ALARM_INSTRUCTION" not in code:
            code = rule_code + code
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"Patched system prompt structure in {path}")
            
            subprocess.run(["git", "add", path])
            patched = True

if patched:
    subprocess.run(["git", "commit", "-m", "Fix: Define system alarm instructions properly for backend"])
    subprocess.run(["git", "push", "origin", "main"])
    print("\nPushed fix to Render! Wait 1 minute for deployment.")
else:
    print("Could not automatically locate prompt structure. Let's check your files manually if needed.")
