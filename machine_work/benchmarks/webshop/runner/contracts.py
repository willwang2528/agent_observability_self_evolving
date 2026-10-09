"""Small, fail-closed boundary between a benchmark environment and model."""
import json
from runtime import summarize_events

def actor_view(state):
    return {key:state[key] for key in ('observation','available_actions') if key in state}

def parse_action(prediction, tools=False):
    action=prediction.get('action')
    if not isinstance(action,str) or not action.strip():raise ValueError('Action must be a nonempty string')
    if not tools:
        if action in ('search','click'):
            try:kwargs=json.loads(prediction['arguments'])
            except (ValueError,KeyError,TypeError) as e:raise ValueError('Invalid WebShop arguments') from e
            keys=('keywords','query') if action=='search' else ('value','target')
            if not isinstance(kwargs,dict) or len(kwargs)!=1:raise ValueError('One native action argument required')
            key=next(iter(kwargs))
            if key not in keys or not isinstance(kwargs[key],str) or not kwargs[key].strip():raise ValueError('Unknown WebShop argument')
            return action+'['+kwargs[key]+']'
        return action
    try:kwargs=json.loads(prediction['arguments'])
    except (ValueError,KeyError,TypeError) as e:raise ValueError('Invalid tool arguments') from e
    if not isinstance(kwargs,dict):raise ValueError('Tool arguments must be object')
    return {'name':action,'kwargs':kwargs}

def validate_model_evidence(events,prediction):
    summary=summarize_events(events)
    if not summary['completed'] or summary['failures'] or summary['tool_item_types']:
        raise ValueError('Missing successful isolated model turn or tool contamination')
    if summary['usage']['input_tokens']<=0 or summary['usage']['output_tokens']<=0:
        raise ValueError('Missing usage evidence')
    messages=[e['item']['text'] for e in events if e.get('type')=='item.completed'
              and e.get('item',{}).get('type')=='agent_message']
    if not messages or json.loads(messages[-1])!=prediction:raise ValueError('Prediction differs from raw model response')
    return True
