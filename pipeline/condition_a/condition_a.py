import time
import json
import anthropic

client = anthropic.Anthropic()


def call_llm_no_tool(prompt: str, model: str = "claude-sonnet-4-6", max_retries: int = 3) -> dict:
    """
    Calls the LLM with no tool access (Condition A) and returns its
    parsed JSON recommendation.

    Retries on transient API errors or malformed JSON responses, since a
    single dropped call or a stray markdown fence shouldn't kill an entire
    schema run.
    """
    last_err = None

    for attempt in range(max_retries):
        try:
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

            result = json.loads(raw_text)

            # Validate the shape we actually depend on downstream, so a
            # malformed-but-parseable response fails loudly here rather
            # than as a KeyError deep inside run_condition_a.py.
            if "recommended_indexes" not in result or "per_query_reasoning" not in result:
                raise ValueError(
                    f"LLM response missing required keys. Got: {list(result.keys())}"
                )

            return result

        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            print(f"[attempt {attempt + 1}/{max_retries}] Bad LLM response: {e}")
        except anthropic.APIError as e:
            last_err = e
            print(f"[attempt {attempt + 1}/{max_retries}] API error: {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    raise ValueError(
        f"LLM call failed after {max_retries} attempts"
    ) from last_err