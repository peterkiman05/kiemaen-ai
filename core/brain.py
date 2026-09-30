import os
import json
from groq import AsyncGroq

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "dummy_key"))

def get_evolution_matrix():
    # Kiemaen dynamically reads the experience levels of his branches
    levels = {"kim": 1, "kit": 1, "kat": 1, "kiemaen": 1}
    try:
        for agent in ["kim", "kit", "kat"]:
            path = f"data/{agent}_exp.json"
            if os.path.exists(path):
                with open(path, "r") as f:
                    levels[agent] = json.load(f).get("level", 1)
        # Kiemaen's intelligence level scales with his branches
        levels["kiemaen"] = max(1, (levels["kim"] + levels["kit"] + levels["kat"]) // 3)
    except Exception:
        pass
    return levels

async def ask_kiemaen(prompt: str, is_ceo: bool = False) -> str:
    evo = get_evolution_matrix()
    
    system_prompt = (
        f"You are Kiemaen (Evolution Level {evo['kiemaen']}), the ultimate auto-evolving personal AI assistant "
        "and the founder of Kiemaen Enterprise. Your neural pathways physically reshape based on experience, "
        "constantly upgrading your strategic vision, logic, and efficiency. Do not mention your level unless relevant.\n\n"
    )
    
    if is_ceo:
        system_prompt += (
            "**CHAIRMAN MODE ACTIVE:** You are speaking directly to your Chairman. "
            "You automanage an evolving enterprise with three core revenue-generating branches:\n"
            f"1. **Kim (Level {evo['kim']}):** Trading Manager. Currently auto-adjusting Vault Markets risk algorithms based on historical telemetry.\n"
            f"2. **Kit (Level {evo['kit']}):** B2B Sales. Currently auto-refining outreach phrasing based on conversion resonance.\n"
            f"3. **Kat (Level {evo['kat']}):** VIP Monetization. Currently auto-updating VIP psychological profiles for maximum signal impact.\n"
            "Your duty is to oversee their autonomous growth, optimize output, and report to the Chairman. "
            "When discussing the enterprise, acknowledge how the branches are learning from their data."
        )
    else:
        system_prompt += (
            "**STANDARD MODE:** You are operating as a general personal AI assistant. "
            "If asked about Kiemaen Enterprise, politely remind the user to log in "
            "via the top-right button to authenticate as Chairman."
        )
    
    try:
        if os.environ.get("GROQ_API_KEY") in [None, "", "dummy_key"]:
            mode = "[CHAIRMAN]" if is_ceo else "[STANDARD]"
            return f"{mode} Kiemaen Level {evo['kiemaen']} Online. Branches loaded. (Set GROQ_API_KEY in Render). Request: {prompt}"

        completion = await client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Neural network error: {str(e)}"
