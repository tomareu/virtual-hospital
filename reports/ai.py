from dataclasses import dataclass

import httpx

REQUEST_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class AIProviderError(Exception):
    pass


@dataclass(frozen=True)
class Completion:
    text: str
    finished: bool
    total_tokens: int | None


class ChatCompletionClient:

    def __init__(self, base_url, api_key, model, transport=None):
        self.model = model
        self._base_url = base_url
        self._headers = {'Authorization': f'Bearer {api_key}'}
        self._transport = transport

    def complete(self, messages, *, max_completion_tokens, temperature, reasoning_effort, response_format):
        payload = {
            'model': self.model,
            'messages': messages,
            'max_completion_tokens': max_completion_tokens,
            'temperature': temperature,
            'reasoning_effort': reasoning_effort,
            'response_format': response_format,
        }
        try:
            with httpx.Client(
                base_url=self._base_url,
                headers=self._headers,
                timeout=REQUEST_TIMEOUT,
                transport=self._transport,
            ) as client:
                response = client.post('chat/completions', json=payload)
                response.raise_for_status()
            data = response.json()
            choice = data['choices'][0]
            return Completion(
                text=choice['message']['content'] or '',
                finished=choice['finish_reason'] == 'stop',
                total_tokens=(data.get('usage') or {}).get('total_tokens'),
            )
        except httpx.HTTPStatusError as error:
            raise AIProviderError(f'HTTP {error.response.status_code}') from error
        except httpx.HTTPError as error:
            raise AIProviderError(type(error).__name__) from error
        except (ValueError, LookupError, TypeError, AttributeError) as error:
            raise AIProviderError('Malformed response') from error
