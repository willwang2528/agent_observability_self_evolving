"""Read-only model-free reruns followed by a fail-closed publication acceptance record."""
from pathlib import Path
import subprocess,json,datetime,os,sys,hashlib,re
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'machine_work/benchmarks'

def main():
    env=os.environ.copy();env['PYTHONPYCACHEPREFIX']='/tmp/benchmark-acceptance-pycache'
    if sys.platform=='darwin' and 'JAVA_HOME' not in env:env['JAVA_HOME']=subprocess.check_output(['/usr/libexec/java_home'],text=True).strip()
    python=ROOT/'.benchmark_cache/venv/bin/python';commands=[
      [python,'-m','unittest','discover','-s',BASE/'_shared','-p','test_*.py','-v'],
      [python,'-m','unittest','discover','-s',BASE/'webshop/runner','-p','test_*.py','-v'],
      [python,'-m','unittest','discover','-s',BASE/'who_when/pilot_20261009/tests','-v'],
      [python,BASE/'_shared/verify_who_when.py'],
      [python,BASE/'_shared/verify.py','alfworld'],
      [python,BASE/'webshop/verify.py'],
      [python,BASE/'_shared/verify.py','tau_bench']]
    logs=BASE/'validation';logs.mkdir(exist_ok=True);checks=[];test_count=0
    for i,cmd in enumerate(commands):
        cmd=[str(x) for x in cmd];r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True)
        log=logs/f'check_{i:02d}.log';log.write_text(r.stdout+r.stderr)
        checks.append({'command':cmd,'returncode':r.returncode,'log':str(log.relative_to(ROOT)),'sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
        if r.returncode:raise RuntimeError('Acceptance failed: '+str(log))
        if i<3:
            match=re.search(r'^Ran (\d+) tests? in ',r.stdout+r.stderr,re.MULTILINE)
            if not match:raise RuntimeError('Missing unittest count: '+str(log))
            test_count+=int(match.group(1))
    names=['who_when','alfworld','webshop','tau_bench'];reports={}
    for name in names:
        p=BASE/name/('acceptance.json' if name=='who_when' else 'results/acceptance.json');x=json.loads(p.read_text());assert x['acceptance']=='PASS'
        reports[name]={'acceptance':'PASS','report':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    data={'acceptance':'PASS','verified_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope':'All selected native feasibility pilots verified; not a full benchmark suite or self-evolution claim',
          'benchmarks':reports,'checks':checks,'unit_tests':test_count,'human_audit':'pending',
          'model_calls_in_this_acceptance':0,'publication_allowed':True}
    (BASE/'ACCEPTANCE.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    print(f'All 4 benchmark archives PASS independent offline acceptance; {test_count} tests passed. No model calls in acceptance.')
if __name__=='__main__':main()
