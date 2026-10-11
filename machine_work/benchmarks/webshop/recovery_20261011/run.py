"""Append-only development recovery attempts on the same two original tasks."""
from pathlib import Path
import argparse,json,hashlib,time,sys,traceback
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'runner'))
from adapters import WebShop,prompt_for
from contracts import actor_view,parse_action
from model import call_model

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(attempt):
    protocol=json.loads((BASE/'protocol.json').read_text())
    runroot=BASE/'results'/attempt;runroot.mkdir(parents=True,exist_ok=False)
    manifest={'started_at':time.time(),'protocol_sha256':sha(BASE/'protocol.json'),'runner_sha256':{str(p.relative_to(BASE)):sha(p) for p in sorted((BASE/'runner').glob('*.py'))},'run_sha256':sha(BASE/'run.py')}
    (runroot/'start.json').write_text(json.dumps(manifest,indent=2))
    outcomes=[]
    for i,task in enumerate(protocol['tasks']):
        case=runroot/f'case_{i:03d}';case.mkdir();env=WebShop(task)
        history=[];steps=[];initial=actor_view(env.view());current=initial
        (case/'trajectory.json').write_text(json.dumps({'task':task,'initial':initial,'steps':steps},ensure_ascii=False,indent=2))
        try:
            for turn in range(protocol['max_steps']):
                pred=call_model(prompt_for(history,current),case/'actor_calls'/f'{turn:03d}')
                action=parse_action(pred,False);response=env.step(action)
                steps.append({'turn':turn,'before':current,'action':action,'after':response})
                history.append({'observation':current['observation'],'action':action})
                (case/'trajectory.json').write_text(json.dumps({'task':task,'initial':initial,'steps':steps},ensure_ascii=False,indent=2))
                print('webshop',task,turn,action,'reward',response['reward'],'done',response['done'],flush=True)
                if response['done']:break
                current=actor_view(env.view())
            score=env.score();(case/'score.json').write_text(json.dumps(score,indent=2));outcomes.append({'task':task,**score})
            print('RESULT',task,score,flush=True)
        except Exception as error:
            (case/'failure.json').write_text(json.dumps({'error':repr(error),'traceback':traceback.format_exc()},indent=2))
            outcomes.append({'task':task,'runtime_failure':repr(error)});print('FAILURE',task,repr(error),flush=True)
        finally:env.close()
    complete={'completed_at':time.time(),'protocol_sha256':sha(BASE/'protocol.json'),'outcomes':outcomes,'all_success':all(x.get('reward')==1 and x.get('done') for x in outcomes)}
    (runroot/'complete.json').write_text(json.dumps(complete,indent=2))
    print('COMPLETE',json.dumps(complete),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);run(p.parse_args().attempt)
