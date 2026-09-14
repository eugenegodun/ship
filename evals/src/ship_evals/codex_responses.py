"""Adapt fixture transcripts to Responses while retaining returned reasoning items."""
from types import SimpleNamespace


def responses_input(messages):
    items = []
    for message in messages:
        if '_responses_output' in message:
            items.extend(message['_responses_output'])
        elif message['role'] == 'tool':
            items.append({'type': 'function_call_output', 'call_id': message['tool_call_id'],
                          'output': message['content']})
        else:
            if message.get('content'):
                items.append({'role': message['role'], 'content': message['content']})
            for call in message.get('tool_calls', []):
                items.append({'type': 'function_call', 'call_id': call['id'],
                              'name': call['function']['name'], 'arguments': call['function']['arguments']})
    return items


def response_view(response):
    output = [item.model_dump(mode='json', exclude_none=True) for item in response.output]
    calls = []
    texts = []
    for item in output:
        if item['type'] == 'function_call':
            calls.append(SimpleNamespace(id=item['call_id'], type='function', function=SimpleNamespace(
                name=item['name'], arguments=item['arguments'])))
        elif item['type'] == 'message':
            texts.extend(part['text'] for part in item['content'] if part['type'] == 'output_text')
    finish = 'tool_calls' if calls else 'stop'
    if response.status != 'completed':
        details = getattr(response, 'incomplete_details', None)
        reason = getattr(details, 'reason', None)
        finish = 'length' if reason == 'max_output_tokens' else response.status
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content='\n'.join(texts) or None, tool_calls=calls), finish_reason=finish)],
        responses_output=output)
