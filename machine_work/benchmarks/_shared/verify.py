"""Independent, offline acceptance: model evidence, official replay and scorer controls."""
import json,hashlib,subprocess,zipfile
from pathlib import Path
from adapters import ROOT,CACHE,ADAPTERS,ReplayUser,alf_env,setup_imports
from contracts import actor_view,parse_action,validate_model_evidence
from runtime import summarize_events

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def check_source(name,protocol):
    source=CACHE/name
    assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==protocol['upstream']['commit']
    assert not subprocess.check_output(['git','-C',str(source),'diff','--stat'],text=True).strip(),'Upstream modified'
    for file,h in protocol['runner_sha256'].items():assert sha(ROOT/'machine_work/benchmarks'/file)==h,('Runner changed',file)
    prov=load(ROOT/'machine_work/benchmarks'/name/'data_provenance.json')
    if name=='webshop':
        for row in prov:
            assert sha(source/'data'/row['file'])==row['mirrors'][0]['sha256']==row['mirrors'][1]['sha256']
    elif name=='tau_bench':
        for row in prov:assert sha(source/row['file'])==row['sha256']
    else:
        for row in prov:
            archive=CACHE/row['url'].split('/')[-1];assert sha(archive)==row['sha256']
        with zipfile.ZipFile(CACHE/'json_2.1.3_tw-pddl.zip') as archive:
            for task in protocol['tasks']:assert hashlib.sha256(archive.read(task)).hexdigest()==sha(CACHE/'alfworld_data'/task)

def check_calls(directory):
    totals={'input_tokens':0,'cached_input_tokens':0,'output_tokens':0};count=0;warnings=set()
    for path in sorted(directory.glob('*/prediction.json')):
        events=[json.loads(s) for s in (path.parent/'events.jsonl').read_text().splitlines() if s.strip()]
        pred=load(path);validate_model_evidence(events,pred)
        summary=summarize_events(events);warnings.update(summary['warnings'])
        assert load(path.parent/'execution.json')['returncode']==0
        for k in totals:totals[k]+=summary['usage'][k]
        count+=1
    for w in warnings:
        assert 'skip_host_skill_discovery' in w or w == 'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.',('Unexpected warning',w)
    return {'calls':count,'usage':totals,'configuration_warnings':sorted(warnings)}

def controls(name,tasks):
    rows=[]
    for task in tasks:
        if name=='alfworld':
            negative=alf_env(task);negative.reset();s,r,d=negative.step('look');negative.close();assert not s['won'] and r==0
            positive=alf_env(task);s=positive.reset()
            actions=load(CACHE/'alfworld_data'/task)['walkthrough']
            assert actions,'Missing official walkthrough'
            for action in actions:s,r,d=positive.step(action)
            positive.close();assert s['won'] and r==1,('Official walkthrough positive control failed',task)
            rows.append({'task':task,'positive_reward':float(r),'negative_reward':0,'positive_actions':actions,'control_source':'walkthrough stored in official game.tw-pddl; never actor input','control_only':True})
        elif name=='webshop':
            e=ADAPTERS[name](task);goal=e.env.server.user_sessions[e.env.session]['goal']
            from web_agent_site.engine.goal import get_reward
            server=e.env.server;target=server.product_item_dict[goal['asin']]
            options=goal['goal_options']
            if isinstance(options,list):options={str(i):v for i,v in enumerate(options)}
            good=get_reward(target,goal,server.product_prices[goal['asin']],options)
            bad=next((get_reward(p,goal,server.product_prices[p['asin']],{}) for p in server.all_products if get_reward(p,goal,server.product_prices[p['asin']],{})==0),None)
            assert good==1 and bad==0,(good,bad)
            rows.append({'task':task,'positive_reward':float(good),'negative_reward':float(bad),'control_only':True});e.close()
        else:
            from tau_bench.types import Action
            negative=ADAPTERS[name](task);neg=negative.score()['reward'];assert neg==0
            positive=ADAPTERS[name](task)
            for a in positive.env.task.actions:positive.env.step(a)
            pos=positive.score()['reward'];assert pos==1
            rows.append({'task':task,'positive_reward':pos,'negative_reward':neg,'control_only':True})
    return rows

def verify(name):
    base=ROOT/'machine_work/benchmarks'/name;protocol=load(base/'protocol.json');check_source(name,protocol)
    runroot=base/'results/run_20261009';complete=load(runroot/'complete.json')
    assert complete['protocol_sha256']==sha(base/'protocol.json')
    cases=sorted(runroot.glob('case_*'));assert len(cases)==len(protocol['tasks'])
    rows=[]
    for case,task in zip(cases,protocol['tasks']):
        trace=load(case/'trajectory.json');assert trace['task']==task
        assert 0<len(trace['steps'])<=protocol['max_steps']
        actor_calls=check_calls(case/'actor_calls');assert actor_calls['calls']==len(trace['steps'])
        user_calls=check_calls(case/'user_calls')
        if name=='tau_bench':assert user_calls['calls']==1+sum(row['action']['name']=='respond' for row in trace['steps'])
        else:assert user_calls['calls']==0
        user=None
        if name=='tau_bench':
            u=[load(p)['action'] for p in sorted((case/'user_calls').glob('*/prediction.json'))]
            assert u;user=ReplayUser(u[0],u[1:])
        env=ADAPTERS[name](task,user);current=actor_view(env.view());assert current==trace['initial']
        history=[]
        try:
            for turn,row in enumerate(trace['steps']):
                assert row['turn']==turn and row['before']==current,('Observation mismatch',name,task,turn)
                directory=case/'actor_calls'/f'{turn:03d}'
                pred=load(directory/'prediction.json');assert parse_action(pred,env.tools)==row['action']
                expected=env.rules+'\n\nObserved interaction so far:\n'+json.dumps(history,ensure_ascii=False)+'\nCurrent observation and available actions:\n'+json.dumps(current,ensure_ascii=False)
                assert (directory/'prompt.txt').read_text()==expected,('Actor prompt mismatch',turn)
                response=env.step(row['action']);assert response==row['after'],('Replay mismatch',name,task,turn,response,row['after'])
                history.append({'observation':current['observation'],'action':row['action']})
                if response['done']:assert turn==len(trace['steps'])-1
                else:current=actor_view(env.view())
            score=env.score();assert score==load(case/'score.json'),('Score mismatch',name,task)
        finally:env.close()
        rows.append({'task':task,'steps':len(trace['steps']),'score':score,'actor':actor_calls,'user':user_calls,'official_replay':'PASS'})
    report={'benchmark':name,'acceptance':'PASS','verifier_sha256':sha(Path(__file__)),'scope':'Two-task native smoke pilot only; not full benchmark score or self-evolution validation',
            'real_model_tasks':len(rows),'successes':sum(x['score']['reward']==1.0 for x in rows),
            'mean_reward':sum(x['score']['reward'] for x in rows)/len(rows),'cases':rows,'scorer_controls':controls(name,protocol['tasks'])}
    (base/'results/acceptance.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(name,'ACCEPTANCE PASS','tasks',len(rows),'successes',report['successes'],'mean reward',report['mean_reward'],flush=True)
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('benchmark',choices=ADAPTERS);verify(p.parse_args().benchmark)
