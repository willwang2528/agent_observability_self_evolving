"""Independent offline verification of every retained repair attempt."""
import hashlib, importlib.util, json, subprocess, sys, re, traceback
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[3]; SHARED=ROOT/'machine_work/benchmarks/_shared'
sys.path.insert(0,str(SHARED))
from adapters import TauBench, ReplayUser
from contracts import actor_view, parse_action, validate_model_evidence
from model import INSTRUCTIONS, SCHEMA
from runtime import build_command, summarize_events
spec=importlib.util.spec_from_file_location('shared_verifier',SHARED/'verify.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
spec=importlib.util.spec_from_file_location('recovery_runner',BASE/'run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check_call(path, expected_prompt):
    assert (path/'prompt.txt').read_text()==expected_prompt,('Prompt mismatch',str(path))
    assert (path/'instructions.txt').read_text()==INSTRUCTIONS,('Instruction mismatch',str(path))
    assert load(path/'schema.json')==SCHEMA
    cmd=load(path/'command.json');cwd=Path(cmd[cmd.index('--cd')+1])
    resolved=cwd.resolve()
    assert cwd.is_absolute() and cwd.name.startswith('benchmark-model-')
    assert str(resolved).startswith(('/private/var/folders/','/private/tmp/','/tmp/')),('Model cwd is not isolated temp',str(cwd))
    assert not resolved.is_relative_to(ROOT.resolve()),'Model cwd must not expose repository'
    assert cmd==build_command(cwd,path/'schema.json',path/'prediction.json',path/'instructions.txt'),('Model command mismatch',str(path))
    events=[json.loads(x) for x in (path/'events.jsonl').read_text().splitlines() if x.strip()]
    summary=summarize_events(events);execution=load(path/'execution.json')
    assert execution['returncode']==0
    for k,v in summary.items():assert execution[k]==v,(str(path),k)
    assert summary['completed'] and not summary['failures'] and not summary['tool_item_types']
    pred=load(path/'prediction.json');validate_model_evidence(events,pred)
    return pred

def confirmation_audit(trace):
    """Necessary explicit assent check, supplemented by the separate semantic audit."""
    confirmations=[]
    for i,row in enumerate(trace['steps']):
        if row['action']['name']!='exchange_delivered_order_items':continue
        prior=[r for r in trace['steps'][:i] if r['action']['name']=='respond']
        assert prior,'No user confirmation before exchange'
        reply=prior[-1]['after']['observation']
        assert re.search(r'\byes\b|\bproceed with\b',reply,re.I),'No explicit assent before exchange'
        assert not re.search(r"\b(don[’']t|do not|cannot|hold off|not confirm|not proceed|before I confirm|only after|provided that|on condition|if you can confirm|if you verify)\b",reply,re.I),'Unresolved user restriction before exchange'
        confirmations.append({'exchange_turn':i,'confirmation_turn':prior[-1]['turn'],'user_reply':reply,'proposal':prior[-1]['action']['kwargs']['content']})
    return confirmations

def incomplete_evidence(attempt):
    rows=[]
    for case in sorted(attempt.glob('case_*')):
        groups={}
        for role in ('actor','user'):
            calls=[];totals={'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}
            for d in sorted((case/f'{role}_calls').glob('*')):
                if not d.is_dir():continue
                execution=load(d/'execution.json') if (d/'execution.json').exists() else None
                calls.append({'call':d.name,'has_prediction':(d/'prediction.json').exists(),'execution':execution})
                if execution:
                    for k in totals:totals[k]+=execution['usage'][k]
            groups[role]={'calls':len(calls),'usage':totals,'records':calls,'incomplete_usage_may_be_unknown':any(x['execution'] is None for x in calls)}
        rows.append({'case':case.name,**groups,'score':load(case/'score.json') if (case/'score.json').exists() else None})
    return rows

def verify_attempt(attempt, protocol):
    assert load(attempt/'started.json')['protocol_sha256']==sha(BASE/'protocol.json')
    if not (attempt/'complete.json').exists():
        assert (attempt/'failed.json').exists(),'Unfinished attempt without failure evidence'
        return {'attempt':attempt.name,'complete':False,'failure':load(attempt/'failed.json'),'successes':None,'cases':incomplete_evidence(attempt)}
    assert not (attempt/'failed.json').exists()
    assert load(attempt/'complete.json')['protocol_sha256']==sha(BASE/'protocol.json')
    cases=sorted(attempt.glob('case_*'));assert len(cases)==len(protocol['tasks'])
    rows=[]
    for case,task in zip(cases,protocol['tasks']):
        trace=load(case/'trajectory.json');assert trace['task']==task
        assert 0<len(trace['steps'])<=protocol['max_steps']
        actor=shared.check_calls(case/'actor_calls');user=shared.check_calls(case/'user_calls')
        assert actor['calls']==len(trace['steps'])
        assert user['calls']==1+sum(r['action']['name']=='respond' for r in trace['steps'])
        assert sorted(p.name for p in (case/'actor_calls').iterdir() if p.is_dir())==[f'{i:03d}' for i in range(actor['calls'])]
        assert sorted(p.name for p in (case/'user_calls').iterdir() if p.is_dir())==[f'{i:03d}' for i in range(user['calls'])]
        users=[load(p)['action'] for p in sorted((case/'user_calls').glob('*/prediction.json'))]
        env=TauBench(task,ReplayUser(users[0],users[1:]));current=actor_view(env.view())
        assert current==trace['initial']
        from tau_bench.envs.user import LLMUserSimulationEnv
        messages=[{'role':'system','content':LLMUserSimulationEnv.build_system_prompt(None,env.env.task.instruction)},
                  {'role':'user','content':'Hi! How can I help you today?'}]
        def verify_user(index):
            expected='Simulate the user. Put your one-line reply in action and {} in arguments.\n'+json.dumps(messages,ensure_ascii=False)
            pred=check_call(case/'user_calls'/f'{index:03d}',expected)
            assert pred['action']==users[index] and json.loads(pred['arguments'])=={}
            messages.append({'role':'assistant','content':users[index]})
        verify_user(0);ui=0;history=[];final_actual_db_hash=None
        for turn,row in enumerate(trace['steps']):
            assert row['turn']==turn and row['before']==current
            pred=check_call(case/'actor_calls'/f'{turn:03d}',runner.actor_prompt(env,history,current))
            assert parse_action(pred,env.tools)==row['action']
            if row['action']['name']=='respond':
                messages.append({'role':'user','content':row['action']['kwargs']['content']});ui+=1;verify_user(ui)
            before_hash=env.env.get_data_hash()
            response=env.step(row['action']);assert response==row['after'],('Replay mismatch',task,turn)
            history.append({'observation':current['observation'],'action':row['action']})
            if response['done']:
                assert turn==len(trace['steps'])-1
                # Terminal respond/transfer do not mutate the DB; official scoring then does.
                assert row['action']['name'] in ('respond','transfer_to_human_agents')
                final_actual_db_hash=before_hash
                assert response['db_hash']==before_hash
            else:current=actor_view(env.view());final_actual_db_hash=env.env.get_data_hash()
        assert ui+1==len(users)
        score=env.score();assert score==load(case/'score.json')
        assert bool(score['official']['info']['r_actions'])==(final_actual_db_hash==score['official']['info']['gt_data_hash'])
        if score['reward']==1:
            assert score['won'] and score['done'] and score['official']['info']['r_actions']==1
            assert final_actual_db_hash==score['official']['info']['gt_data_hash']
        rows.append({'task':task,'steps':len(trace['steps']),'score':score,'actor':actor,'user':user,'confirmation_evidence':confirmation_audit(trace),
          'official_replay':'PASS','final_actual_db_hash':final_actual_db_hash,
          'user_prompt_reconstruction':'PASS','actor_prompt_and_runtime_reconstruction':'PASS'})
    return {'attempt':attempt.name,'complete':True,'successes':sum(r['score']['reward']==1 for r in rows),'cases':rows}

def verify():
    protocol=load(BASE/'protocol.json');assert protocol['tasks']==[0,1]
    shared.check_source('tau_bench',protocol)
    source=ROOT/'.benchmark_cache/tau_bench'
    assert not subprocess.check_output(['git','-C',str(source),'diff','HEAD','--'],text=True).strip(),'Upstream tracked source changed'
    assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=all'],text=True).strip(),'Upstream untracked/staged/source modification'
    for name,h in protocol['recovery_sha256'].items():assert sha(BASE/name)==h,('Frozen recovery file changed',name)
    original={str(f.relative_to(BASE.parent)):sha(f) for f in sorted((BASE.parent/'results/run_20261009').rglob('*')) if f.is_file()}
    assert original==protocol['original_run_sha256'],'Original evidence changed'
    attempts=[verify_attempt(a,protocol) for a in sorted((BASE/'results').glob('attempt_*')) if a.is_dir()]
    assert attempts,'No real attempt'
    selected=attempts[-1]
    assert selected['complete'] and selected['successes']==2,'Latest complete fixed-pair attempt did not achieve 2/2'
    report={'benchmark':'tau_bench','acceptance':'PASS','real_model_tasks':2,'successes':2,'mean_reward':1.0,
      'scope':'Observed failure repair/development set. Same two original test indices; adaptive attempts are not independent benchmark accuracy or self-evolution evidence.',
      'selected_attempt':selected['attempt'],'all_attempts':attempts,'cases':selected['cases'],
      'scorer_controls':shared.controls('tau_bench',[0,1]),'original_run_preserved':'PASS',
      'official_source_and_data_unchanged':'PASS','verifier_sha256':sha(Path(__file__)),'protocol_sha256':sha(BASE/'protocol.json')}
    (BASE/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('tau_bench RECOVERY PASS',selected['attempt'],'2/2 successful, raw calls and full official replay verified')
    return report

if __name__=='__main__':
    try:verify()
    except BaseException as exc:
        (BASE/'acceptance.json').write_text(json.dumps({'benchmark':'tau_bench','acceptance':'FAIL','error':repr(exc),'traceback':traceback.format_exc()},indent=2)+'\n')
        raise
