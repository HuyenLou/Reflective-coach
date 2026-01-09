"""LLM integration with Anthropic Claude."""

import json
import re
import logging
from typing import Optional, Dict, Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings

logger = logging.getLogger(__name__)

# Maximum retries for JSON parsing failures
MAX_RETRIES = 2


def get_llm() -> ChatAnthropic:
    """Get configured LLM instance."""
    settings = get_settings()
    return ChatAnthropic(
        model=settings.model_name,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        api_key=settings.anthropic_api_key
    )


async def generate_coach_response(
    system_prompt: str,
    phase_prompt: str
) -> str:
    """
    Generate a coaching response using the LLM.

    Args:
        system_prompt: The core coaching persona prompt
        phase_prompt: The phase-specific prompt with context

    Returns:
        The coach's response text
    """
    llm = get_llm()

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=phase_prompt)
    ]

    response = await llm.ainvoke(messages)
    return response.content


async def generate_reflection(
    reflection_prompt: str
) -> Dict[str, Any]:
    """
    Generate a post-session reflection using the LLM.

    Includes retry logic for JSON parsing failures.

    Args:
        reflection_prompt: The full reflection generation prompt

    Returns:
        Parsed reflection dictionary
    """
    llm = get_llm()

    messages = [
        HumanMessage(content=reflection_prompt)
    ]

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.ainvoke(messages)
            result = parse_json_response(response.content)

            # Validate required fields
            if "error" not in result and validate_reflection_schema(result):
                return result

            # If parsing failed or validation failed, retry
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"Reflection parsing attempt {attempt + 1} failed, retrying..."
                )
                # Add instruction to return valid JSON on retry
                messages = [
                    HumanMessage(
                        content=reflection_prompt +
                        "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations."
                    )
                ]
            else:
                last_error = result.get("error", "Validation failed")

        except Exception as e:
            last_error = str(e)
            logger.error(f"LLM call failed on attempt {attempt + 1}: {e}")
            if attempt >= MAX_RETRIES:
                break

    # Return fallback with error info
    logger.error(f"Reflection generation failed after {MAX_RETRIES + 1} attempts: {last_error}")
    return {
        "key_observations": "Unable to generate observations due to processing error.",
        "outcome_classification": "partial_progress",
        "insights_summary": "Session completed but reflection generation encountered an error.",
        "commitment": None,
        "suggested_followup": None,
        "error": last_error
    }


def validate_reflection_schema(data: Dict[str, Any]) -> bool:
    """
    Validate that reflection data has required fields.

    Args:
        data: Parsed reflection dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["key_observations", "outcome_classification", "insights_summary"]

    for field in required_fields:
        if field not in data or not data[field]:
            return False

    # Validate outcome classification
    valid_outcomes = ["breakthrough_achieved", "partial_progress", "root_cause_identified"]
    if data.get("outcome_classification") not in valid_outcomes:
        return False

    return True


async def check_transition(
    transition_prompt: str
) -> Dict[str, Any]:
    """
    Check if we should transition to the next phase.

    Includes error handling with fallback to conservative decision.

    Args:
        transition_prompt: The phase transition prompt

    Returns:
        Transition decision dictionary
    """
    settings = get_settings()

    # Use a faster model for transition checks
    llm = ChatAnthropic(
        model=settings.model_name,
        temperature=0.3,  # Lower temperature for more consistent decisions
        max_tokens=256,
        api_key=settings.anthropic_api_key
    )

    messages = [
        HumanMessage(content=transition_prompt)
    ]

    try:
        response = await llm.ainvoke(messages)
        result = parse_json_response(response.content)

        # Validate transition response structure
        if "error" not in result and "should_transition" in result:
            return result

        # Invalid response - return conservative decision (don't transition)
        logger.warning(f"Invalid transition response: {result}")
        return {
            "should_transition": False,
            "next_phase": None,
            "reasoning": "Invalid LLM response - staying in current phase"
        }

    except Exception as e:
        logger.error(f"Transition check failed: {e}")
        # On error, return conservative decision
        return {
            "should_transition": False,
            "next_phase": None,
            "reasoning": f"LLM error - staying in current phase: {str(e)}"
        }


async def extract_observations(
    messages_text: str,
    existing_observations: str,
    extract_commitment: bool = False,
    existing_commitment: str = "",
    existing_key_insight: str = ""
) -> Dict[str, str]:
    """
    Extract observations from recent conversation.
    Optionally extracts commitment and key_insight during CHALLENGE phase.

    Args:
        messages_text: Recent messages text
        existing_observations: Previously identified observations
        extract_commitment: Whether to also extract commitment/key_insight (CHALLENGE phase)
        existing_commitment: Previously identified commitment
        existing_key_insight: Previously identified key insight

    Returns:
        Dict with observations, commitment, and key_insight
    """
    llm = get_llm()

    if extract_commitment:
        # Full extraction during CHALLENGE phase
        prompt = f"""Analyze these recent coaching messages and extract insights.

### Recent Messages
{messages_text}

### Existing State
Observations: {existing_observations or "(None yet)"}
Commitment: {existing_commitment or "(None yet)"}
Key Insight: {existing_key_insight or "(None yet)"}

### Task
Extract the following from this exchange:

1. **observations**: Note any NEW patterns, fears, beliefs, or strengths revealed (1-3 sentences). Build on existing observations.
2. **commitment**: If the user made a specific commitment (action + timeframe), capture it verbatim. Look for phrases like "I will...", "I commit to...", "I'm going to...". If no new commitment, return the existing one or empty string.
3. **key_insight**: If there was an "aha moment" or core realization, capture it. Look for shifts in thinking or breakthrough statements. If no new insight, return the existing one or empty string.

### Response Format
Return JSON only (no markdown, no explanation):
{{"observations": "...", "commitment": "...", "key_insight": "..."}}"""

        messages = [HumanMessage(content=prompt)]

        try:
            response = await llm.ainvoke(messages)
            result = parse_json_response(response.content)

            if "error" not in result:
                return {
                    "observations": result.get("observations", existing_observations) or existing_observations,
                    "commitment": result.get("commitment", existing_commitment) or existing_commitment,
                    "key_insight": result.get("key_insight", existing_key_insight) or existing_key_insight
                }
        except Exception as e:
            logger.warning(f"Full extraction failed, falling back: {e}")

        # Fallback: return existing values
        return {
            "observations": existing_observations,
            "commitment": existing_commitment,
            "key_insight": existing_key_insight
        }

    else:
        # Simple observations-only extraction (EXPLORATION phase)
        prompt = f"""Analyze these recent coaching messages and identify any new observations about the learner.

### Recent Messages
{messages_text}

### Existing Observations
{existing_observations or "(None yet)"}

### Task
Briefly note any NEW patterns, fears, beliefs, or strengths revealed in this exchange.
Keep it concise (1-3 sentences). If nothing new, just return the existing observations.

### Response
Return only the updated observations text (no JSON, no formatting):"""

        messages = [HumanMessage(content=prompt)]

        try:
            response = await llm.ainvoke(messages)
            return {
                "observations": response.content.strip(),
                "commitment": existing_commitment,
                "key_insight": existing_key_insight
            }
        except Exception as e:
            logger.warning(f"Observation extraction failed: {e}")
            return {
                "observations": existing_observations,
                "commitment": existing_commitment,
                "key_insight": existing_key_insight
            }


def parse_json_response(text: str) -> Dict[str, Any]:
    """
    Parse JSON from LLM response, handling markdown code blocks.

    Args:
        text: Raw LLM response text

    Returns:
        Parsed dictionary
    """
    # Try to find JSON in code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to parse the whole thing
        json_str = text

    # Clean up common issues
    json_str = json_str.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to extract just the JSON object
        brace_match = re.search(r'\{[\s\S]*\}', json_str)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        # Return a default structure if parsing fails
        return {
            "error": "Failed to parse JSON",
            "raw_response": text[:500]
        }
