"""Fail-closed, no-LLM official replay; successful execution alone never passes."""
from pathlib import Path
import argparse,json,hashlib,subprocess,sys,time,traceback,tempfile
if not __debug__:raise RuntimeError('Verification requires assertions; PYTHONOPTIMIZE/-O is forbidden')
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'runner'))
from adapters import ROOT,CACHE,WebShop,prompt_for
from contracts import actor_view,parse_action,validate_model_evidence
from runtime import build_command,summarize_events
from model import SCHEMA,INSTRUCTIONS

def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(CACHE/'webshop'),*args],text=True).strip()
def check_source(protocol):
    assert git('rev-parse','HEAD')==protocol['upstream']['commit'],'Official commit changed'
    assert not git('status','--porcelain','--untracked-files=all'),'Official source dirty, staged or untracked'
    assert not git('diff','--cached','--stat'),'Official staged source changed'
    for row in load(BASE.parent/'data_provenance.json'):
        assert sha(CACHE/'webshop/data'/row['file'])==row['mirrors'][0]['sha256']==row['mirrors'][1]['sha256'],('Data changed',row['file'])
    old_manifest=load(BASE/'original_run_sha256.json')
    original_files={str(p.relative_to(BASE.parent)) for p in (BASE.parent/'results/run_20261009').rglob('*') if p.is_file()}
    assert set(old_manifest)==original_files,'Original file inventory changed'
    for file,digest in old_manifest.items():assert sha(BASE.parent/file)==digest,('Original result changed',file)

def check_call(directory):
    assert {p.name for p in directory.iterdir() if p.is_file()}=={'prompt.txt','schema.json','instructions.txt','isolation.json','command.json','events.jsonl','stderr.txt','prediction.json','execution.json'},('Missing or extra call evidence',directory)
    assert load(directory/'schema.json')==SCHEMA,'Schema changed'
    assert (directory/'instructions.txt').read_text()==INSTRUCTIONS,'System instructions changed'
    command=load(directory/'command.json');isolation=load(directory/'isolation.json')
    cwd=Path(isolation['cwd'])
    assert cwd.name.startswith('benchmark-model-') and cwd.is_absolute(),'Unexpected model cwd'
    assert cwd.parent.resolve() in {Path(tempfile.gettempdir()).resolve(),Path('/tmp').resolve()},'Model cwd is outside allowed temporary roots'
    assert str(ROOT) not in str(cwd) and isolation=={'cwd':str(cwd),'initial_entries':[],'repository_context':False},'Model context isolation failed'
    assert command==build_command(cwd,directory/'schema.json',directory/'prediction.json',directory/'instructions.txt'),'Model command/settings changed'
    events=[json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines() if s.strip()]
    prediction=load(directory/'prediction.json');validate_model_evidence(events,prediction)
    summary=summarize_events(events);execution=load(directory/'execution.json')
    assert execution['returncode']==0 and execution['wall_seconds']>0,'Model execution failed'
    assert all(execution[k]==v for k,v in summary.items()),'Saved execution summary differs from raw events'
    for warning in summary['warnings']:
        assert 'skip_host_skill_discovery' in warning or warning=='Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.',('Unexpected runtime warning',warning)
    return prediction,summary

def verify_attempt(attempt,protocol):
    complete=load(attempt/'complete.json');start=load(attempt/'start.json')
    assert complete['protocol_sha256']==start['protocol_sha256']==sha(BASE/'protocol.json'),'Protocol changed across run'
    for file,digest in start['runner_sha256'].items():assert sha(BASE/file)==digest,('Actor runner changed after execution',file)
    assert start['run_sha256']==sha(BASE/'run.py'),'Run entrypoint changed'
    cases=sorted(attempt.glob('case_*'));assert len(cases)==len(protocol['tasks'])
    rows=[]
    for case,task in zip(cases,protocol['tasks']):
        assert not (case/'failure.json').exists(),'Runtime failure retained; no acceptance for incomplete attempt'
        trace=load(case/'trajectory.json');assert trace['task']==task
        assert 0<len(trace['steps'])<=protocol['max_steps']
        directories=sorted(p for p in (case/'actor_calls').iterdir() if p.is_dir())
        assert [p.name for p in directories]==[f'{i:03d}' for i in range(len(trace['steps']))],'Calls and transitions differ'
        usage={'input_tokens':0,'cached_input_tokens':0,'output_tokens':0};warnings=set()
        env=WebShop(task);current=actor_view(env.view());assert current==trace['initial'];history=[]
        try:
            for turn,row in enumerate(trace['steps']):
                assert row['turn']==turn and row['before']==current,('Observation mismatch',task,turn)
                directory=directories[turn];pred,summary=check_call(directory)
                assert parse_action(pred,False)==row['action'],('Raw model action not executed',task,turn)
                assert (directory/'prompt.txt').read_text()==prompt_for(history,current),('Actor prompt differs from observation-only allowlist',task,turn)
                response=env.step(row['action']);assert response==row['after'],('Official transition replay mismatch',task,turn)
                history.append({'observation':current['observation'],'action':row['action']})
                for k in usage:usage[k]+=summary['usage'][k]
                warnings.update(summary['warnings'])
                if response['done']:assert turn==len(trace['steps'])-1,'Post-terminal model call'
                else:current=actor_view(env.view())
            score=env.score();assert score==load(case/'score.json'),('Official score mismatch',task)
            if score['done']:
                from web_agent_site.engine.goal import get_reward
                server=env.env.server;session=server.user_sessions[env.env.session]
                reward,detail=get_reward(server.product_item_dict[session['asin']],session['goal'],server.product_prices[session['asin']],session['options'],verbose=True)
                assert reward==score['reward'],'Official reward breakdown differs'
                breakdown={'source':'Official get_reward(verbose=True), computed only after rollout by offline replay; never actor input','purchased_asin':session['asin'],'purchased_options':session['options'],'official_breakdown':detail,'reward':float(reward)}
                if (case/'reward_breakdown.json').exists():assert load(case/'reward_breakdown.json')==breakdown,'Saved reward breakdown differs'
                else:(case/'reward_breakdown.json').write_text(json.dumps(breakdown,indent=2,ensure_ascii=False)+'\n')
        finally:env.close()
        rows.append({'task':task,'steps':len(trace['steps']),'score':score,'official_replay':'PASS','actor':{'calls':len(directories),'usage':usage,'configuration_warnings':sorted(warnings),'raw_actions_and_settings':'PASS','observation_only_prompt':'PASS','empty_cwd_no_tools':'PASS'}})
    all_success=all(row['score']=={'reward':1.0,'won':True,'done':True} for row in rows)
    assert complete['all_success']==all_success,'Recorded success flag mismatch'
    assert complete['outcomes']==[{'task':row['task'],**row['score']} for row in rows],'Recorded outcomes mismatch'
    return {'attempt':attempt.name,'integrity':'PASS','all_success':all_success,'successes':sum(row['score']['reward']==1 for row in rows),'cases':rows}

def scorer_controls(protocol):
    rows=[]
    for task in protocol['tasks']:
        env=WebShop(task)
        try:
            from web_agent_site.engine.goal import get_reward
            server=env.env.server;goal=server.user_sessions[env.env.session]['goal'];target=server.product_item_dict[goal['asin']]
            options=goal['goal_options'];options={str(i):value for i,value in enumerate(options)} if isinstance(options,list) else options
            positive=get_reward(target,goal,server.product_prices[goal['asin']],options)
            negative=next((get_reward(p,goal,server.product_prices[p['asin']],{}) for p in server.all_products if get_reward(p,goal,server.product_prices[p['asin']],{})==0),None)
            assert positive==1 and negative==0,'Official scorer controls failed'
            rows.append({'task':task,'positive_reward':float(positive),'negative_reward':float(negative),'control_only':True,'actor_never_receives_control_inputs':True})
        finally:env.close()
    return rows

def success_gate(selected):
    assert selected['integrity']=='PASS' and selected['all_success'] and selected['successes']==2,'Both original tasks must fully succeed in one complete attempt'
    assert [x['task'] for x in selected['cases']]==[0,1],'Original task IDs changed'
    for row in selected['cases']:
        assert row['score']=={'reward':1.0,'won':True,'done':True},'Partial reward is not success'
        assert row['official_replay']=='PASS' and row['actor']['calls']>0,'No verified model rollout'

def verify(selected_name=None):
    protocol=load(BASE/'protocol.json');assert protocol['tasks']==[0,1] and protocol['model']=='gpt-6-astra' and protocol['reasoning_effort']=='xhigh'
    check_source(protocol)
    attempts=sorted(p for p in (BASE/'results').glob('attempt_*') if p.is_dir());assert attempts,'No recovery attempts'
    reports=[verify_attempt(p,protocol) for p in attempts]
    selected=next((x for x in reports if x['attempt']==selected_name),None) if selected_name else reports[-1]
    assert selected is not None,'Selected attempt absent';success_gate(selected)
    report={'benchmark':'webshop','acceptance':'PASS','verified_at_unix':time.time(),'verifier_sha256':sha(Path(__file__)),'protocol_sha256':sha(BASE/'protocol.json'),'scope':'Development recovery on the same two previously observed tasks, not held-out performance or full-suite reproduction','selected_attempt':selected['attempt'],'all_attempts':reports,'real_model_tasks':2,'successes':2,'mean_reward':1.0,'cases':selected['cases'],'all_attempt_actor_calls':sum(row['actor']['calls'] for a in reports for row in a['cases']),'scorer_controls':scorer_controls(protocol),'original_run_unchanged':True,'official_source_and_data':'PASS'}
    (BASE/'acceptance.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('WEB SHOP RECOVERY ACCEPTANCE PASS',selected['attempt'],'2/2 fully successful; all-attempt model calls',report['all_attempt_actor_calls'],flush=True)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt');args=p.parse_args()
    try:verify(args.attempt)
    except Exception as error:
        (BASE/'acceptance.json').write_text(json.dumps({'benchmark':'webshop','acceptance':'FAIL','error':repr(error),'verified_at_unix':time.time()},indent=2)+'\n')
        raise
