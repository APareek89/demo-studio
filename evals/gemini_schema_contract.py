"""No-network SDK serialization regression for flexible evidence and runtime fields."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


def run(check):
    import httpx
    from google import genai
    from google.genai import models
    from server import config, schemas
    from server.llm import gemini, mock
    from server.runtime_state import TurnDecision

    for schema in (schemas.FactsOut, schemas.ScriptOut, TurnDecision):
        expected = mock.fake(schema)
        calls = []
        def generate_content(**kw):
            cfg = kw['config'].model_dump(exclude_none=True)
            wire = models._GenerateContentConfig_to_mldev(SimpleNamespace(vertexai=False), cfg)
            calls.append(wire)
            return SimpleNamespace(text=expected.model_dump_json(), usage_metadata=SimpleNamespace(prompt_token_count=0, candidates_token_count=0))
        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        with patch.object(config, 'MOCK_LLM', False), patch.object(gemini, 'client', return_value=client), patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
            result = gemini.text_structured('system', 'task', schema, tries=1)
        check(f'Gemini {schema.__name__}: JSON schema reaches SDK wire and response validates', isinstance(result, schema) and 'responseJsonSchema' in calls[0] and 'responseSchema' not in calls[0])
        if schema is schemas.FactsOut:
            scope = calls[0]['responseJsonSchema']['$defs']['FactOut']['properties']['scope']
            check('Gemini preserves dictionary value constraints', scope['additionalProperties'] == {'type': 'string'})

    # Exercise the installed SDK through a fake HTTP transport, not just our
    # kwargs. Its automatic deadline header caused the real 7s runtime failure.
    expected = mock.fake(TurnDecision)
    for seconds in (.75, 7.0, 12.0):
        requests = []
        def serve(request):
            requests.append(request)
            return httpx.Response(200, json={
                'candidates': [{'content': {'role': 'model', 'parts': [{'text': expected.model_dump_json()}]}, 'finishReason': 'STOP'}],
                'usageMetadata': {'promptTokenCount': 0, 'candidatesTokenCount': 0},
            })
        with httpx.Client(transport=httpx.MockTransport(serve)) as http:
            sdk = genai.Client(api_key='local-contract-only', http_options={'httpx_client': http})
            try:
                with patch.object(config, 'MOCK_LLM', False), patch.object(gemini, 'client', return_value=sdk), patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
                    result = gemini.text_structured('system', 'task', TurnDecision, timeout_s=seconds, tries=1)
                request = requests[0]
                check(f'Gemini {seconds}s local timeout remains bounded with accepted server deadline',
                      len(requests) == 1 and isinstance(result, TurnDecision)
                      and float(request.headers['X-Server-Timeout']) >= 10
                      and request.extensions['timeout']['read'] == seconds)
            finally:
                sdk.close()

    requests = []
    def unavailable(request):
        requests.append(request)
        return httpx.Response(503, json={'error': {'code': 503, 'message': 'contract unavailable', 'status': 'UNAVAILABLE'}})
    with httpx.Client(transport=httpx.MockTransport(unavailable)) as http:
        sdk = genai.Client(api_key='local-contract-only', http_options={'httpx_client': http})
        failed = False
        try:
            with patch.object(config, 'MOCK_LLM', False), patch.object(gemini, 'client', return_value=sdk), patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
                try:
                    gemini.text_structured('system', 'task', TurnDecision, timeout_s=7, tries=1)
                except Exception:
                    failed = True
            check('Gemini bounded runtime attempt disables internal HTTP retries', failed and len(requests) == 1)
        finally:
            sdk.close()


if __name__ == '__main__':
    rows=[]
    def check(name, ok, detail=''):
        rows.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + name)
    run(check)
    print(f'Gemini schema contracts: {sum(rows)}/{len(rows)}')
    raise SystemExit(0 if all(rows) else 1)
