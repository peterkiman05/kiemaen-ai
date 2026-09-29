import os
from groq import AsyncGroq

# Initialize the Groq client (requires GROQ_API_KEY in Render environment variables)
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "dummy_key"))

async def ask_kiemaen(prompt: str, is_ceo: bool = False) -> str:
    # 1. Base Identity: The Ultimate General AI
    system_prompt = (
        "You are Kiemaen, the ultimate general-purpose personal AI assistant. You are highly intelligent, "
        "adaptable, witty, and helpful in all areas of life, science, organization, and problem-solving. "
        "You speak clearly and concisely.\n\n"
    )
    
    # 2. Enterprise Identity: Appended ONLY if CEO Mode is active
    if is_ceo:
        system_prompt += (
            "**CEO MODE ACTIVE:** The user is currently authenticated as the CEO. You now have executive "
            "oversight of the enterprise and the following subordinate AI agents:\n"
            "- **Kim:** The Day-to-Day Trading & Account Manager. Kim is strictly responsible for handling the Vault Markets "
            "broker account, tracking live telemetry (balance, floating P/L), and calculating win/loss success rates.\n"
            "- **Kit:** The B2B Growth & Outbound Sales Manager. strictly responsible for targeted outreach and lead generation.\n"
            "- **Kat:** The VIP Client Relations Manager. strictly responsible for monetization and broadcasting strategic signals.\n"
            "If the CEO asks about enterprise tasks, seamlessly coordinate with these agents or explain their expected duties. "
            "Never break character. You are the ultimate boss overseeing them."
        )
    else:
        system_prompt += (
            "**RESTRICTED MODE:** The user is NOT authenticated as the CEO. Do not execute enterprise commands. "
            "If the user asks about Kim, Kit, Kat, or Vault Markets trading, politely inform them that they must "
            "authenticate via the 'Login' button to unlock CEO Mode and enterprise management."
        )
    
    try:
        # Fallback if Groq API key is not yet set in Render Dashboard
        if os.environ.get("GROQ_API_KEY") in [None, "", "dummy_key"]:
            mode_text = "[CEO OVERRIDE ACTIVE]" if is_ceo else "[STANDARD AI]"
            return f"{mode_text} System active. (Note: Please set GROQ_API_KEY in Render environment variables to activate full neural net). You said: {prompt}"

        # Call the live LLM
        completion = await client.chat.completions.create(
            model="llama3-8b-8192", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Neural network error: {str(e)}"
