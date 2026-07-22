import anthropic
import json

client = anthropic.Anthropic()

def call_llm_no_tool(prompt: str, model: str = "claude-sonnet-4-6") -> dict:
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
        # Deliberately: no `tools` parameter passed at all.
        # This is what makes this Condition A, not Condition B.
    )

    raw_text = response.content[0].text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON:\n{raw_text}") from e
