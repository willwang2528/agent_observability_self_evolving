"""Offline re-acceptance of the archived Who&When pilot after directory migration."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'machine_work/benchmarks/who_when'
PILOT=BASE/'pilot_20261009';sys.path.insert(0,str(PILOT))
from score_results import score_directory
from runtime import summarize_events

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((PILOT/'PUBLICATION_MANIFEST.json').read_text());checked=0
    for row in manifest['included_source_files']:
        if row['path']=='README.md':continue # portable invocation paths intentionally updated
        assert sha(PILOT/row['path'])==row['sha256'],row['path'];checked+=1
    metrics,rows=score_directory(PILOT)
    assert metrics==json.loads((PILOT/'results/metrics.json').read_text())
    plan=json.loads((PILOT/'results/plan.json').read_text());calls=0
    for job in plan['jobs']:
        d=PILOT/'results/runs'/job['job_id'];result=json.loads((d/'result.json').read_text())
        assert sha(d/'prompt.txt')==job['prompt_sha256']==result['prompt_sha256']
        attempts=sorted(d.glob('attempt_*'));assert len(attempts)==1
        a=attempts[0];events=[json.loads(s) for s in (a/'events.jsonl').read_text().splitlines() if s.strip()]
        summary=summarize_events(events)
        assert summary['completed'] and not summary['failures'] and not summary['tool_item_types']
        assert summary['usage']==result['usage'] and summary['usage']['output_tokens']>0
        messages=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
        assert messages and json.loads(messages[-1])==json.loads((a/'response.json').read_text())==result['prediction']
        calls+=1
    assert calls==24 and metrics['planned_cases']==12
    report={'benchmark':'who_when','acceptance':'PASS','scope':'Archived 12-task, 24-call no-answer-assisted diagnosis adaptation; newly verified without model rerun',
        'source_file_hashes_verified_excluding_readme':checked,'real_model_calls':calls,'planned_cases':12,
        'conditions':{c:{'n':g['n'],'joint_correct':g['counts']['joint'],'abstained':g['abstained']} for c,g in metrics['groups']['all'].items()},
        'raw_event_recount':'PASS','frozen_metrics_recalculation':'PASS','original_gold_unchanged':True,'human_review':'pending'}
    (BASE/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
