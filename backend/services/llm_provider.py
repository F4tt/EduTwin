from __future__ import annotations

import os
from typing import Dict, List, Optional

import httpx
import asyncio
import time
from typing import Any
import logging

from core.logging_config import get_logger
from core.metrics import track_tokens, llm_requests_total, llm_request_duration_seconds, llm_errors_total, llm_retries_total

logger = get_logger(__name__)


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "generic").lower()
LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


class LLMProvider:
    """Simple provider abstraction. Supports 'gemini' and a generic HTTP-post provider that
    accepts `model` and `messages` in JSON body. The user will provide `LLM_API_URL` and `LLM_API_KEY`.
    """

    def __init__(self):
        self.provider = LLM_PROVIDER
        self.api_url = LLM_API_URL
        self.api_key = LLM_API_KEY
        self.model = LLM_MODEL
        self.timeout = LLM_TIMEOUT
        # concurrency limit to avoid too many parallel requests to the provider
        self._concurrency = int(os.getenv("LLM_CONCURRENCY", "6"))
        # semaphore created lazily for asyncio usage
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Optional[dict]:
        if not self.api_url:
            logger.warning("LLM API URL not configured")
            return None
        
        headers = {"Content-Type": "application/json"}

        # create semaphore if needed
        if self._semaphore is None:
            # create one semaphore per event loop
            self._semaphore = asyncio.Semaphore(self._concurrency)

        max_retries = int(os.getenv("LLM_RETRIES", "3"))
        base_backoff = float(os.getenv("LLM_BACKOFF_SECONDS", "0.8"))

        start_time = time.time()
        status = "success"
        error_type = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # limit concurrency to avoid bursts
            async with self._semaphore:
                attempt = 0
                while True:
                    attempt += 1
                    try:
                        if self.provider == "gemini":
                            # Official Google Generative AI API format (v1beta generateContent)
                            # Converts OpenAI-like messages (role/content) into Google's contents format (role/parts)
                            # See: https://ai.google.dev/api/rest/v1beta/models/generateContent
                            
                            contents: List[Dict[str, Any]] = []
                            for m in messages:
                                role = m.get("role", "user")
                                content_text = m.get("content", "")
                                
                                # Map roles: system messages become user messages with context
                                if role == "system":
                                    # System prompts go as user content in Gemini
                                    contents.append({
                                        "role": "user",
                                        "parts": [{"text": content_text}]
                                    })
                                elif role == "user":
                                    contents.append({
                                        "role": "user",
                                        "parts": [{"text": content_text}]
                                    })
                                elif role == "assistant":
                                    contents.append({
                                        "role": "model",
                                        "parts": [{"text": content_text}]
                                    })

                            payload = {
                                "contents": contents,
                                "generationConfig": {
                                    "temperature": temperature,
                                    "maxOutputTokens": 8096,
                                }
                            }

                            url = self.api_url
                            if self.api_key:
                                sep = "&" if "?" in url else "?"
                                url = f"{url}{sep}key={self.api_key}"

                            logger.info(f"Sending Gemini request (attempt {attempt})", extra={
                                "provider": self.provider,
                                "model": self.model,
                                "temperature": temperature,
                                "message_count": len(messages)
                            })
                            resp = await client.post(url, json=payload, headers=headers)
                        else:
                            # generic: OpenAI-like shape
                            if self.api_key:
                                headers["Authorization"] = f"Bearer {self.api_key}"
                            payload = {"model": self.model, "messages": messages, "temperature": temperature}
                            
                            logger.info(f"Sending LLM request (attempt {attempt})", extra={
                                "provider": self.provider,
                                "model": self.model,
                                "temperature": temperature,
                                "message_count": len(messages)
                            })
                            resp = await client.post(self.api_url, json=payload, headers=headers)

                        # Handle response codes: retry on transient service-unavailable or rate-limit
                        if resp.status_code >= 500 or resp.status_code == 429:
                            if attempt <= max_retries:
                                backoff = base_backoff * (2 ** (attempt - 1))
                                # small jitter
                                backoff = backoff * (0.8 + 0.4 * (time.time() % 1))
                                
                                logger.warning(f"LLM request failed with status {resp.status_code}, retrying", extra={
                                    "provider": self.provider,
                                    "model": self.model,
                                    "status_code": resp.status_code,
                                    "attempt": attempt,
                                    "backoff": backoff
                                })
                                
                                # Track retry
                                llm_retries_total.labels(
                                    provider=self.provider,
                                    model=self.model
                                ).inc()
                                
                                await asyncio.sleep(backoff)
                                continue
                            else:
                                status = "error"
                                error_type = f"http_{resp.status_code}"
                                logger.error(f"LLM request failed after {attempt} attempts", extra={
                                    "provider": self.provider,
                                    "model": self.model,
                                    "status_code": resp.status_code,
                                    "response": resp.text[:500]
                                })
                                raise RuntimeError(f"LLM API returned {resp.status_code}: {resp.text}")

                        if resp.status_code >= 400:
                            status = "error"
                            error_type = f"http_{resp.status_code}"
                            logger.error(f"LLM request error", extra={
                                "provider": self.provider,
                                "model": self.model,
                                "status_code": resp.status_code,
                                "response": resp.text[:500]
                            })
                            raise RuntimeError(f"LLM API returned {resp.status_code}: {resp.text}")

                        response_data = resp.json()
                        
                        # Extract and track token usage
                        self._track_token_usage(response_data)
                        
                        logger.info("LLM request successful", extra={
                            "provider": self.provider,
                            "model": self.model,
                            "duration": time.time() - start_time,
                            "attempt": attempt
                        })
                        
                        return response_data

                    except (httpx.RequestError, httpx.TimeoutException) as exc:
                        # network error -> retry up to max_retries
                        if attempt <= max_retries:
                            backoff = base_backoff * (2 ** (attempt - 1))
                            
                            logger.warning(f"LLM request network error, retrying", extra={
                                "provider": self.provider,
                                "model": self.model,
                                "error": str(exc),
                                "attempt": attempt,
                                "backoff": backoff
                            })
                            
                            # Track retry
                            llm_retries_total.labels(
                                provider=self.provider,
                                model=self.model
                            ).inc()
                            
                            await asyncio.sleep(backoff)
                            continue
                        
                        status = "error"
                        error_type = type(exc).__name__
                        logger.error(f"LLM request failed after {attempt} attempts", extra={
                            "provider": self.provider,
                            "model": self.model,
                            "error": str(exc)
                        })
                        raise RuntimeError(f"LLM request failed after {attempt} attempts: {exc}")
                    
                    finally:
                        # Track metrics
                        duration = time.time() - start_time
                        
                        llm_requests_total.labels(
                            provider=self.provider,
                            model=self.model,
                            status=status
                        ).inc()
                        
                        llm_request_duration_seconds.labels(
                            provider=self.provider,
                            model=self.model
                        ).observe(duration)
                        
                        if error_type:
                            llm_errors_total.labels(
                                provider=self.provider,
                                model=self.model,
                                error_type=error_type
                            ).inc()
    
    def _track_token_usage(self, response_data: dict):
        """Extract and track token usage from LLM response."""
        try:
            # OpenAI format
            usage = response_data.get("usage")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                if total_tokens > 0:
                    logger.info("Token usage tracked", extra={
                        "provider": self.provider,
                        "model": self.model,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    })
                    
                    track_tokens(
                        provider=self.provider,
                        model=self.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens
                    )
                    return
            
            # Google Gemini format
            metadata = response_data.get("usageMetadata")
            if metadata:
                prompt_tokens = metadata.get("promptTokenCount", 0)
                completion_tokens = metadata.get("candidatesTokenCount", 0)
                total_tokens = metadata.get("totalTokenCount", 0)
                
                if total_tokens > 0:
                    logger.info("Token usage tracked (Gemini)", extra={
                        "provider": self.provider,
                        "model": self.model,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    })
                    
                    track_tokens(
                        provider=self.provider,
                        model=self.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens
                    )
                    return
            
            # If no usage data found, estimate based on text length (rough approximation)
            # This is a fallback and won't be very accurate
            logger.debug("No token usage data in response, skipping token tracking")
            
        except Exception as e:
            logger.warning(f"Failed to track token usage: {e}", extra={
                "provider": self.provider,
                "model": self.model
            })


# Singleton
_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = LLMProvider()
    return _provider
