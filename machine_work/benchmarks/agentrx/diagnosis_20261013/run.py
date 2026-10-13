"""Fixed, append-only AgentRx diagnosis run. Never retry based on diagnosis scores."""
import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone

import jsonschema
import protocol
from runtime import build_command, CODEX_BINARY, MODEL, REASONING_EFFORT

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'upstream/data/tau_retail/tau_dataset_failed.json'
SOURCE_COMMIT = '7a18c79708e7671be15124460f4f7296107c2a55'
SCHEMA = {'type':'object', 'additionalProperties':False,
          'properties':{k:{'type':'string'} for k in ['taxonomy_checklist_reasoning','reason_for_failure','reason_for_index']},
          'required':['taxonomy_checklist_reasoning','reason_for_failure','failure_case','reason_for_index','index']}
SCHEMA['properties'].update({'failure_case':{'type':'integer','minimum':0,'maximum':10}, 'index':{'type':'integer'}})
KNOWN_WARNINGS = [
 'Under-development features enabled: skip_host_skill_discovery. Under-development features are incomplete and may behave unpredictably. To suppress this warning, set `suppress_unstable_features_warning = true` in /Users/will/.codex/config.toml.',
 'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.'
]

def now(): return datetime.now(timezone.utc).isoformat()
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, obj): Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
def read(p): return json.loads(Path(p).read_text())

def inspect_attempt(folder):
    """Recompute status from original files; summary.json is never trusted."""
    metadata = read(folder/'metadata.json')
    events=[]; malformed=[]
    for i,line in enumerate((folder/'events.jsonl').read_text().splitlines(),1):
        try: events.append(json.loads(line))
        except (ValueError,TypeError): malformed.append(i)
    errors=[]; warnings=[]; tools=[]; final=[]; completed=[]
    for e in events:
        typ=e.get('type')
        if typ in ['turn.failed','error']: errors.append(e)
        if typ=='turn.completed': completed.append(e)
        if typ in ['item.started','item.updated','item.completed']:
            item=e.get('item',{}); kind=item.get('type')
            if kind=='error':
                msg=item.get('message','')
                if msg in KNOWN_WARNINGS: warnings.append(msg)
                else: errors.append(e)
            elif kind not in ['agent_message','reasoning']: tools.append(kind)
            if typ=='item.completed' and kind=='agent_message': final.append(item.get('text',''))
        elif typ not in ['thread.started','turn.started','turn.completed','turn.failed','error']:
            errors.append({'unrecognized_event':e})
    response=None; schema_error=None; final_matches=False
    try:
        response=read(folder/'response.json'); jsonschema.validate(response,SCHEMA)
        final_matches = len(final)==1 and json.loads(final[0])==response
    except Exception as exc: schema_error=str(exc)
    usage=completed[0].get('usage',{}) if len(completed)==1 else {}
    usable=(metadata['exit_code']==0 and not metadata['timed_out'] and len(completed)==1
            and not malformed and not errors and not tools and not schema_error and final_matches
            and usage.get('input_tokens',0)>0 and usage.get('output_tokens',0)>0)
    return {'usable':usable,'exit_code':metadata['exit_code'],'timed_out':metadata['timed_out'],
            'completed_turns':len(completed),'malformed_lines':malformed,'errors':errors,
            'tool_item_types':tools,'known_warnings':sorted(set(warnings)),
            'schema_error':schema_error,'final_matches':final_matches,'usage':usage}

def frozen_files():
    paths=[ROOT/n for n in ['run.py','score.py','protocol.py','runtime.py','test_events.py','test_protocol.py','system_prompt.txt','schema.json']]
    paths += sorted((ROOT/'upstream').rglob('*'))
    paths += sorted((ROOT/'inputs').rglob('*'))
    return {str(p.relative_to(ROOT)):digest(p) for p in paths if p.is_file()}

def prepare():
    assert not (ROOT/'plan.json').exists(), 'Plan already exists: no overwrite permitted'
    inputs=protocol.build_inputs(RAW)
    assert len(inputs)==29 and len({str(x['task_id']) for x in inputs})==29
    (ROOT/'inputs').mkdir(exist_ok=False)
    (ROOT/'system_prompt.txt').write_text(protocol.system_prompt())
    dump(ROOT/'schema.json',SCHEMA)
    cases=[]
    for x in sorted(inputs,key=lambda x:int(x['task_id'])):
        tid=str(x['task_id']); steps=x['steps']; prompt=x['user_prompt']
        assert [s['index'] for s in steps]==list(range(1,len(steps)+1))
        folder=ROOT/'inputs'/tid; folder.mkdir()
        dump(folder/'steps.json',steps); (folder/'prompt.txt').write_text(prompt)
        cases.append({'task_id':tid,'steps':len(steps),'prompt_characters':len(prompt),
                      'prompt_sha256':digest(folder/'prompt.txt')})
    version=subprocess.check_output([CODEX_BINARY,'--version'],text=True).strip()
    plan={'created_at':now(),'benchmark':'AgentRx','split':'tau-retail, entire public failed set',
          'source_url':'https://github.com/microsoft/AgentRx','source_commit':SOURCE_COMMIT,
          'method':'official baseline prompt, full official IR steps, one diagnostic call per trajectory',
          'model':MODEL,'reasoning_effort':REASONING_EFFORT,'cli_binary':CODEX_BINARY,'cli_version':version,
          'timeout_seconds':600,'max_attempts':2,'workers':3,
          'retry_rule':'Only failed transport/event/schema checks. Never inspect accuracy to retry.',
          'diagnosis_gold':'Scoring only; not read by prepare or run; no diagnosis labels in model input.',
          'input_adaptation':'Official system text via Codex model_instructions_file; official Conversation repr via stdin; structured output transport.',
          'not_supplied':['task.instruction','task.actions','task.outputs','reward','reward_info','root_cause labels','few-shot examples','invariant violations'],
          'cases':cases,'frozen_files':frozen_files(),
          'dependencies':{lib:importlib.metadata.version(lib) for lib in ['jsonschema']}}
    dump(ROOT/'plan.json',plan)
    print(json.dumps({'prepared':len(cases),'max_input_chars':max(c['prompt_characters'] for c in cases),'version':version}))

def verify_frozen(check_runtime=False):
    plan=read(ROOT/'plan.json')
    for rel,expected in plan['frozen_files'].items():
        assert digest(ROOT/rel)==expected, f'Frozen file changed: {rel}'
    assert plan['model']==MODEL and plan['reasoning_effort']==REASONING_EFFORT
    if check_runtime:
        assert subprocess.check_output([CODEX_BINARY,'--version'],text=True).strip()==plan['cli_version']
    return plan

def environment():
    # Keep account auth in Codex home; do not forward unrelated service secrets.
    return {k:v for k,v in os.environ.items()
            if not any(s in k.upper() for s in ['API_KEY','SECRET','ACCESS_TOKEN'])
            and (not k.startswith('CODEX_') or k=='CODEX_HOME')}

def execute(case,plan):
    tid=case['task_id']; base=ROOT/'calls'/tid; base.mkdir(parents=True,exist_ok=True)
    prior=sorted(base.glob('attempt_*'))
    for attempt in prior:
        status=inspect_attempt(attempt)
        if status['usable']: return {'task_id':tid,'status':'valid','attempt':attempt.name,'resumed':True}
    prompt=(ROOT/'inputs'/tid/'prompt.txt').read_text()
    for number in range(len(prior)+1,plan['max_attempts']+1):
        folder=base/f'attempt_{number}'; folder.mkdir(exist_ok=False)
        with tempfile.TemporaryDirectory(prefix='agentrx-isolated-') as empty:
            command=build_command(Path(empty),ROOT/'schema.json',folder/'response.json',ROOT/'system_prompt.txt')
            metadata={'task_id':tid,'attempt':number,'started_at':now(),'command':command,
                      'prompt_sha256':digest(ROOT/'inputs'/tid/'prompt.txt'),
                      'plan_sha256':digest(ROOT/'plan.json'),'timed_out':False,'exit_code':None}
            dump(folder/'metadata.json',metadata)
            start=time.monotonic()
            with (folder/'events.jsonl').open('w') as out,(folder/'stderr.log').open('w') as err:
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,
                                         text=True,env=environment(),start_new_session=True)
                try: process.communicate(prompt,timeout=plan['timeout_seconds'])
                except subprocess.TimeoutExpired:
                    metadata['timed_out']=True
                    os.killpg(process.pid,signal.SIGTERM)
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL); process.wait()
            metadata.update(exit_code=process.returncode,finished_at=now(),elapsed_seconds=round(time.monotonic()-start,3))
            dump(folder/'metadata.json',metadata)
        status=inspect_attempt(folder); dump(folder/'validation.json',status)
        print(json.dumps({'task_id':tid,'attempt':number,'usable':status['usable'],'elapsed_seconds':metadata['elapsed_seconds'],'usage':status['usage']}),flush=True)
        if status['usable']: return {'task_id':tid,'status':'valid','attempt':folder.name}
    return {'task_id':tid,'status':'failed','attempts':len(list(base.glob('attempt_*')))}

def run(limit=None):
    plan=verify_frozen(check_runtime=True); cases=plan['cases'] if limit is None else plan['cases'][:limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=plan['workers']) as pool:
        results=list(pool.map(lambda c:execute(c,plan),cases))
    snapshot={'updated_at':now(),'planned':len(plan['cases']),'executed_this_invocation':len(cases),'results':results}
    # Append instead of overwriting earlier status.
    with (ROOT/'execution_history.jsonl').open('a') as f: f.write(json.dumps(snapshot)+'\n')
    if any(x['status']!='valid' for x in results): raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['prepare','run','verify-frozen']); parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    if args.command=='prepare': prepare()
    elif args.command=='verify-frozen': verify_frozen(); print('Frozen source/input/runtime hashes unchanged')
    else: run(args.limit)
