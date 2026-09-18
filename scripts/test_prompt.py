import asyncio
import httpx
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.prompts import SYSTEM_PROMPT
from app.core.config import settings

async def main():
    headers = {
        'Authorization': f'Bearer {settings.LLM_API_KEY}',
        'Content-Type': 'application/json'
    }
    user_prompt = (
        "Campus Battery Capacity: 100 kWh\n\n"
        "Operator Notes to interpret (1 notes total):\n"
        "NOTE 0: \"The football event is postponed, solar output is reduced by 30 percent at hour 10, and keep grid usage below 50 kWh.\"\n\n"
        "Return a JSON object with 'directive_interpretation'.\n"
        "CRITICAL RULES:\n"
        "1. When a note contains an unrelated announcement clause ('The football event is postponed...') combined with actionable energy directives, output a separate entry for the announcement first with directive_type: 'no_op', applies: false, structured_adjustment: null (referencing that note's note_index), followed by the active directives for that note!\n"
        "2. 'at hour 10' applies to both solar reduction (factor: 0.7, hours: [10]) and grid limit (max_grid_kwh: 50, hours: [10])."
    )

    payload = {
        'model': settings.LLM_MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt}
        ],
        'response_format': {'type': 'json_object'}
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post('https://api.openai.com/v1/chat/completions', headers=headers, json=payload)
        print(r.json()['choices'][0]['message']['content'])

asyncio.run(main())
