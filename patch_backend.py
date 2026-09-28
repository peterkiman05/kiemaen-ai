import os

target_file = None
for path in ["core/brain.py", "main.py", "agent.py", "core/agent.py"]:
    if os.path.exists(path):
        target_file = path
        break

if not target_file:
    print("Could not find brain/main file automatically.")
else:
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    alarm_instruction = "\n# AUTONOMOUS HARDWARE RULE:\n# If the user asks to set an alarm or wake up, you MUST include the tag [ALARM:HH:MM] in 24-hour format within your response (e.g., 'Setting your alarm now. [ALARM:07:00]').\n"

    if "ALARM:HH:MM" not in content:
        # Append rule to the file or system prompt definition
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(alarm_instruction)
        print(f"Successfully injected alarm rules into {target_file}")
        
        import subprocess
        subprocess.run(["git", "add", target_file])
        subprocess.run(["git", "commit", "-m", "Feature: Add hardware alarm tag instructions to backend LLM"])
        subprocess.run(["git", "push", "origin", "main"])
        print("Pushed update to Render! Wait 1 minute for deployment.")
    else:
        print("Alarm rules already exist in code.")
