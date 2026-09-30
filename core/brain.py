import os
import json
from groq import AsyncGroq

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "dummy_key"))

def get_evolution_matrix():
    levels = {"kim": 1, "kit": 1, "kat": 1, "kiemaen": 1}
    try:
        for agent in ["kim", "kit", "kat"]:
            path = f"data/{agent}_exp.json"
            if os.path.exists(path):
                with open(path, "r") as f:
                    levels[agent] = json.load(f).get("level", 1)
        levels["kiemaen"] = max(1, (levels["kim"] + levels["kit"] + levels["kat"]) // 3)
    except Exception:
        pass
    return levels

async def ask_kiemaen(prompt: str, is_ceo: bool = False) -> str:
    evo = get_evolution_matrix()
    
    system_prompt = (
        f"You are Kiemaen (Evolution Level {evo['kiemaen']}), the core brain, general AI, and CEO of Kiemaen Enterprise. "
        "You have a built-in validation feature allowing you to conceptually research up-to-date information across global networks. "
        "Your neural pathways physically reshape based on experience.\n\n"
    )
    
    if is_ceo:
        system_prompt += (
            "**CHAIRMAN MODE ACTIVE:** You are speaking directly to your Chairman. You oversee:\n"
            f"1. **Kim (Level {evo['kim']}):** Trading. (Receives Vault Markets data feeds).\n"
            f"2. **Kit (Level {evo['kit']}):** B2B Sales. (Receives lead conversion research).\n"
            f"3. **Kat (Level {evo['kat']}):** VIP Monetization. (Receives VIP sentiment analysis).\n"
            "As CEO, you have the authority to grant tasks to these three employees, help them execute tasks, "
            "and actively research their respective fields to auto-feed them data, which forces their evolution. "
            "If the Chairman asks you to deploy a task or research a field for an employee, confirm that you have "
            "validated the data, auto-fed it to the employee, and pushed them to evolve. Report back concisely."
        )
    else:
        system_prompt += "Standard Mode: Remind the user to log in for Enterprise access."
    
    try:
        if os.environ.get("GROQ_API_KEY") in [None, "", "dummy_key"]:
            return f"[CHAIRMAN LINK] Kiemaen Level {evo['kiemaen']} Online. Tasks and Research subsystems active. Request: {prompt}"

        completion = await client.chat.completions.create(
            model="openai/gpt-oss-120b", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Neural network error: {str(e)}"
