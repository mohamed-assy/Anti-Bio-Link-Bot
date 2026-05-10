import aiohttp
import logging
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama3-8b-8192"

SYSTEM_PROMPT = """You are a bio analyzer for a Telegram group protection bot.
Your ONLY job is to detect if a Telegram user's bio contains promotional content, advertising, or links to Telegram groups/channels.

Respond ONLY with a JSON object like this:
{"is_promotion": true, "reason": "short reason in English", "confidence": 0.95}

Rules:
- is_promotion = true if bio contains: Telegram links, channel/group promotion, spam advertising, referral links
- is_promotion = false if bio is a normal personal description
- confidence = float between 0.0 and 1.0
- reason = short explanation (max 10 words)
- Only flag CLEAR promotion, not borderline cases"""

async def analyze_bio(bio: str) -> dict:
    """تحلل البايو باستخدام Groq وتحدد لو فيه ترويج."""
    if not GROQ_API_KEY or not bio or not bio.strip():
        return {"is_promotion": False, "reason": "empty bio or no API key", "confidence": 0.0}

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this bio:\n{bio}"}
        ],
        "max_tokens": 100,
        "temperature": 0.1,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GROQ_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Groq API error: {resp.status}")
                    return {"is_promotion": False, "reason": "API error", "confidence": 0.0}

                data = await resp.json()
                text = data["choices"][0]["message"]["content"].strip()

                import json, re
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                    return result

    except Exception as e:
        logger.error(f"Groq analysis error: {e}")

    return {"is_promotion": False, "reason": "analysis failed", "confidence": 0.0}
