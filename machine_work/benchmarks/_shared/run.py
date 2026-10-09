"""Run the frozen feasibility protocol; no score-conditioned retries or gold actor input."""
import argparse,json,hashlib,time
from pathlib import Path
from contracts import actor_view,parse_action
from model import call_model
from adapters import ROOT,ADAPTERS,CodexUser

def run(name):
    base=ROOT/'machine_work/benchmarks'/name
    protocol=json.loads((base/'protocol.json').read_text());runroot=base/'results/run_20261009'
    runroot.mkdir(parents=True,exist_ok=False)
    for i,task in enumerate(protocol['tasks']):
        case=runroot/f'case_{i:03d}';case.mkdir()
        user=CodexUser(case/'user_calls') if name=='tau_bench' else None
        env=ADAPTERS[name](task,user);history=[];steps=[]
        initial=actor_view(env.view());current=initial
        try:
            for turn in range(protocol['max_steps']):
                prompt=env.rules+'\n\nObserved interaction so far:\n'+json.dumps(history,ensure_ascii=False)+'\nCurrent observation and available actions:\n'+json.dumps(current,ensure_ascii=False)
                pred=call_model(prompt,case/'actor_calls'/f'{turn:03d}')
                action=parse_action(pred,env.tools);response=env.step(action)
                row={'turn':turn,'before':current,'action':action,'after':response}
                steps.append(row);history.append({'observation':current['observation'],'action':action})
                (case/'trajectory.json').write_text(json.dumps({'task':task,'initial':initial,'steps':steps},ensure_ascii=False,indent=2))
                print(name,i,turn,str(action)[:170],'reward',response['reward'],'done',response['done'],flush=True)
                if response['done']:break
                current=actor_view(env.view())
            score=env.score();(case/'score.json').write_text(json.dumps(score,indent=2))
            print('RESULT',name,i,score['reward'],flush=True)
        finally:env.close()
    (runroot/'complete.json').write_text(json.dumps({'completed_at':time.time(),'protocol_sha256':hashlib.sha256((base/'protocol.json').read_bytes()).hexdigest()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('benchmark',choices=ADAPTERS);run(p.parse_args().benchmark)
