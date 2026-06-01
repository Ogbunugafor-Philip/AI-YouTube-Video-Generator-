"""Standalone connectivity test for the fal.ai LLM (fal-ai/any-llm).

Loads fal credentials/models from .env, makes a single call, and prints the
response plus SUCCESS / FAILED.
"""
import os
import traceback

from dotenv import load_dotenv

load_dotenv("/root/projects/vid_gen/.env")

FAL_API_KEY = os.getenv("FAL_API_KEY")
FAL_LLM_MODEL = os.getenv("FAL_LLM_MODEL")
FAL_LLM_CHAT_MODEL = os.getenv("FAL_LLM_CHAT_MODEL")

# fal_client authenticates from the FAL_KEY environment variable.
os.environ["FAL_KEY"] = FAL_API_KEY or ""

PROMPT = (
    "Write a 3 sentence introduction for a YouTube video about how AI is "
    "changing Nigerian banking. Use a warm, clear, engaging voice."
)


def main() -> None:
    print(f"FAL_LLM_MODEL      = {FAL_LLM_MODEL}")
    print(f"FAL_LLM_CHAT_MODEL = {FAL_LLM_CHAT_MODEL}")
    print(f"FAL_API_KEY set    = {bool(FAL_API_KEY)}")
    print("-" * 60)
    try:
        import fal_client

        result = fal_client.subscribe(
            "fal-ai/any-llm",
            arguments={
                "model": FAL_LLM_CHAT_MODEL,
                "prompt": PROMPT,
            },
        )
        # any-llm returns {"output": "...", "reasoning": ..., "error": ...}
        text = ""
        if isinstance(result, dict):
            text = result.get("output") or result.get("text") or ""
        print("RESPONSE TEXT:")
        print(text)
        print("-" * 60)
        if text and text.strip():
            print("SUCCESS")
        else:
            print("FAILED")
            print("Raw result:", result)
    except Exception:
        print("FAILED")
        traceback.print_exc()


if __name__ == "__main__":
    main()
