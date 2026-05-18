"""Robust JSON parsing utilities for handling malformed/truncated LLM output."""
import json
import re
import logging
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


def parse_llm_json(response: str, max_retries: int = 3) -> Optional[Union[dict, list]]:
    """
    Parse JSON from LLM response with multiple fallback strategies.

    Handles:
    - Markdown code blocks (```json ... ```)
    - Truncated JSON at end
    - Unterminated strings
    - Missing closing braces/brackets
    - trailing commas

    Args:
        response: Raw text from LLM
        max_retries: Number of repair attempts

    Returns:
        Parsed JSON (dict or list) or None if all strategies fail
    """
    if not response:
        logger.warning("Empty response received")
        return None

    # Step 1: Basic cleanup
    cleaned = response.strip()

    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Step 2: Direct parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.debug(f"Direct parse failed: {e}")

    # Step 3: Extract JSON from text using regex
    extracted = _extract_json_block(cleaned)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # Step 4: Attempt JSON repair for truncated output
    for attempt in range(max_retries):
        repaired = _repair_json(cleaned, attempt)
        if repaired:
            try:
                result = json.loads(repaired)
                logger.info(f"Successfully repaired JSON on attempt {attempt + 1}")
                return result
            except json.JSONDecodeError:
                continue

    # Step 5: Last resort - try to parse as array with partial objects
    partial = _extract_partial_objects(cleaned)
    if partial:
        logger.warning("Returning partial JSON results")
        return partial

    logger.error(f"All JSON parsing strategies failed. Response: {cleaned[:200]}...")
    return None


def _extract_json_block(text: str) -> Optional[str]:
    """Extract JSON block from text using regex patterns."""
    patterns = [
        # Match JSON object blocks
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
        # Match JSON array blocks
        r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',
        # Look for content between braces/brackets
        r'(\{[\s\S]*\}|\[[\s\S]*\])',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Verify it's valid JSON by checking balanced braces
            if _is_balanced(match):
                return match

    return None


def _is_balanced(text: str) -> bool:
    """Check if JSON braces/brackets are balanced."""
    stack = []
    opening = set(['{', '['])
    closing = {'}': '{', ']': '['}

    for char in text:
        if char in opening:
            stack.append(char)
        elif char in closing:
            if not stack:
                return False
            expected = closing[char]
            if stack.pop() != expected:
                return False
    return len(stack) == 0


def _repair_json(text: str, attempt: int) -> Optional[str]:
    """
    Attempt to repair truncated JSON based on attempt number.

    Strategies:
    - attempt 0: Fix unterminated strings by adding closing quote
    - attempt 1: Add missing closing braces
    - attempt 2: Remove trailing commas
    """
    repaired = text

    if attempt == 0:
        # Fix unterminated strings - add closing quote at end if missing
        # This handles cases like: {"key": "value (cut off here
        last_quote_idx = repaired.rfind('"')
        if last_quote_idx > repaired.rfind('}') or last_quote_idx > repaired.rfind(']'):
            # Check if there's an odd number of quotes after last brace/bracket
            after_bracket = max(repaired.rfind('}'), repaired.rfind(']'))
            if after_bracket > -1:
                quote_count = repaired[after_bracket+1:].count('"')
                if quote_count % 2 == 1:
                    repaired = repaired[:last_quote_idx+1] + '}'

    elif attempt == 1:
        # Add missing closing braces/brackets
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        repaired = repaired + ']' * open_brackets + '}' * open_braces

    elif attempt == 2:
        # Remove trailing commas before closing braces
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
        # Fix missing quotes around keys
        repaired = re.sub(r'(\w+):', r'"\1":', repaired)

    return repaired if _is_balanced(repaired) else None


def _extract_partial_objects(text: str) -> Optional[list]:
    """
    Last resort: extract individual JSON objects from text.
    Returns a list of successfully parsed objects.
    """
    objects = []

    # Find all potential object/array patterns
    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(pattern, text)

    for match in matches:
        try:
            obj = json.loads(match)
            objects.append(obj)
        except json.JSONDecodeError:
            continue

    return objects if objects else None