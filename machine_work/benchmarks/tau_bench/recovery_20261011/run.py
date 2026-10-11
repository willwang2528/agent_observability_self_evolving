"""Development repair runs. Same fixed tasks; every attempt is retained."""
import argparse, hashlib, json, sys, time, traceback
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[3]
SHARED=ROOT/'machine_work/benchmarks/_shared'
sys.path.insert(0,str(SHARED))
from adapters import TauBench, CodexUser
from contracts import actor_view, parse_action
from model import call_model


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def dump(path, obj): Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def actor_prompt(env, history, current):
    return env.rules+'\n\n'+(BASE/'actor_strategy.txt').read_text()+'\nObserved interaction so far:\n'+json.dumps(history,ensure_ascii=False)+'\nCurrent observation and available actions:\n'+json.dumps(current,ensure_ascii=False)

def freeze():
    p=load(BASE.parent/'protocol.json')
    p.update({'frozen_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
      'purpose':'Repair/development on the two previously observed failures; not independent evaluation or self-evolution effectiveness',
      'retry_policy':'Each explicitly numbered development attempt reruns both tasks fresh and is retained regardless of reward. No action substitution, user reply forcing, score rewriting or sample replacement.',
      'actor_change':'General neutral clarification of customer wording versus exact catalog option before confirmation; official policy retained verbatim. No product or task-specific aliases, IDs or answers in strategy.',
      'user_change':'None: original CodexUser with official LLMUserSimulationEnv system prompt and full genuine conversation.',
      'success_gate':'Both fixed tasks [0,1] in one complete attempt have official reward 1.0 and replay passes; all earlier attempts disclosed.',
      'recovery_sha256':{n:sha(BASE/n) for n in ('run.py','actor_strategy.txt')},
      'original_run_sha256':{str(f.relative_to(BASE.parent)):sha(f) for f in sorted((BASE.parent/'results/run_20261009').rglob('*')) if f.is_file()}})
    if (BASE/'protocol.json').exists():
        old=load(BASE/'protocol.json')
        assert old['recovery_sha256']==p['recovery_sha256'],'Frozen code changed; create a new version instead'
        return old
    dump(BASE/'protocol.json',p); return p

def run(attempt):
    protocol=freeze(); runroot=BASE/'results'/attempt;runroot.mkdir(parents=True,exist_ok=False)
    started=time.time()
    dump(runroot/'started.json',{'started_at':started,'protocol_sha256':sha(BASE/'protocol.json')})
    try:
        for i,task in enumerate(protocol['tasks']):
            case=runroot/f'case_{i:03d}';case.mkdir()
            user=CodexUser(case/'user_calls');env=TauBench(task,user);history=[];steps=[]
            initial=actor_view(env.view());current=initial
            for turn in range(protocol['max_steps']):
                pred=call_model(actor_prompt(env,history,current),case/'actor_calls'/f'{turn:03d}')
                action=parse_action(pred,env.tools); response=env.step(action)
                steps.append({'turn':turn,'before':current,'action':action,'after':response})
                history.append({'observation':current['observation'],'action':action})
                dump(case/'trajectory.json',{'task':task,'initial':initial,'steps':steps})
                print(attempt,task,turn,json.dumps(action,ensure_ascii=False),'reward',response['reward'],'done',response['done'],flush=True)
                if response['done']: break
                current=actor_view(env.view())
            score=env.score();dump(case/'score.json',score);env.close()
            print('RESULT',attempt,task,score['reward'],flush=True)
        dump(runroot/'complete.json',{'completed_at':time.time(),'protocol_sha256':sha(BASE/'protocol.json')})
    except BaseException as exc:
        dump(runroot/'failed.json',{'error':repr(exc),'traceback':traceback.format_exc(),'failed_at':time.time()})
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('attempt');args=p.parse_args()
    assert args.attempt.startswith('attempt_') and args.attempt.replace('_','').isalnum()
    run(args.attempt)
