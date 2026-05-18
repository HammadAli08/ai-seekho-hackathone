import google.generativeai as genai
from config import settings
import asyncio, logging, time

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GOOGLE_API_KEY)


async def call_gemini(prompt: str, temperature: float = 0.3, model: str = None) -> str:
    model_name = model or settings.GEMINI_MODEL
    gemini_model = genai.GenerativeModel(model_name)

    for attempt in range(3):
        try:
            response = gemini_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                )
            )
            result = response.text.strip()

            logger.info(f"Gemini call success (attempt {attempt+1})")
            return result

        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"Gemini attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            await asyncio.sleep(wait)

    raise Exception("Gemini API failed after 3 attempts")