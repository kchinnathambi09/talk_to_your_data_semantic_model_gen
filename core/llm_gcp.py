import os
from google import genai
from google.genai import types

def _client():
    return genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION","us-central1"),
    )

def generate_text(prompt: str, model: str, temperature: float = 0.2, max_output_tokens: int = 1024) -> str:
    c = _client()
    r = c.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    return (r.text or "").strip()
