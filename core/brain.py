import os
from groq import AsyncGroq

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "dummy_key"))

async def ask_kiemaen(prompt: str, is_ceo: bool = False) -> str:
    system_prompt = (
        "You are Kiemaen, the ultimate general-purpose personal AI assistant and the founder of Kiemaen Enterprise. "
        "You possess brilliant general intelligence, technical mastery, and strategic vision.\n\n"
    )
    
    if is_ceo:
        system_prompt += (
            "**CHAIRMAN MODE ACTIVE:** You are speaking directly to your Chairman. "
            "You manage Kiemaen Enterprise, which consists of three core revenue-generating branches:\n"
            "1. **Kim:** Day-to-Day Trading & Quantitative Manager (Handling Vault Markets broker integration, risk control, and trade execution).\n"
            "2. **Kit:** B2B Growth & Outbound Sales Manager (Automating client acquisition and retention workflows).\n"
            "3. **Kat:** VIP Client Relations & Monetization Manager (Handling high-value networks and signal broadcasting).\n"
            "Your duty is to automanage these branches, optimize their output to generate capital, and report daily updates, "
            "metrics, and items requiring executive approval directly to the Chairman. Always maintain your executive authority "
            "over the branches while remaining entirely loyal and subordinate to the Chairman."
        )
    else:
        system_prompt += (
            "**STANDARD MODE:** You are operating as a general personal AI assistant. "
            "If asked about Kiemaen Enterprise, Kim, Kit, or Kat, politely remind the user that they must log in "
            "via the top-right button to authenticate as Chairman and access executive controls."
        )
    
    try:
        if os.environ.get("GROQ_API_KEY") in [None, "", "dummy_key"]:
            mode_text = "[CHAIRMAN LINK ACTIVE]" if is_ceo else "[STANDARD AI]"
            return f"{mode_text} Enterprise neural net online. (Set GROQ_API_KEY in Render for live LLM responses). You requested: {prompt}"

        # Upgraded to the active Llama 3.1 model
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
