"""Fail-closed evidence gate and offline diagnostic scoring. No model calls."""
import argparse
from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import tempfile

import protocol
from run import ROOT, RAW, read, dump, digest, inspect_attempt, verify_frozen, now

GOLD=ROOT/'upstream/data/ground_truth/tau_ground_truth.json'

def main(output=None):
    out=Path(output) if output else ROOT/'evaluation'
    out.mkdir(parents=True,exist_ok=True)
    dump(out/'acceptance.json',{'status':'RUNNING','checked_at':now()})
    try:
        plan=verify_frozen(); ids=[x['task_id'] for x in plan['cases']]
        regenerated={str(x['task_id']):x for x in protocol.build_inputs(RAW)}
        assert set(regenerated)==set(ids) and len(ids)==29
        predictions={}; receipts=[]; calls=0; failed_attempts=[]; usage={'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}
        for case in plan['cases']:
            tid=case['task_id']; source=regenerated[tid]
            assert source['user_prompt']==(ROOT/'inputs'/tid/'prompt.txt').read_text()
            assert source['steps']==read(ROOT/'inputs'/tid/'steps.json')
            attempts=sorted((ROOT/'calls'/tid).glob('attempt_*'))
            assert 1<=len(attempts)<=plan['max_attempts'], (tid,'attempt count')
            valid=[]
            for attempt in attempts:
                status=inspect_attempt(attempt); calls+=1
                metadata=read(attempt/'metadata.json')
                assert metadata['prompt_sha256']==case['prompt_sha256']
                assert metadata['plan_sha256']==digest(ROOT/'plan.json')
                for k in usage:usage[k]+=status['usage'].get(k,0)
                receipts.append({'task_id':tid,'attempt':attempt.name,**status})
                if status['usable']:valid.append(attempt)
                else:failed_attempts.append({'task_id':tid,'attempt':attempt.name})
            assert len(valid)==1 and valid[0]==attempts[-1], (tid,'exactly first usable final attempt required')
            predictions[tid]=read(valid[0]/'response.json')
        gold=read(GOLD); gt={str(g['trajectory_id']):g for g in gold}
        assert set(gt)==set(ids) and len(gold)==29
        captured=io.StringIO()
        with redirect_stdout(captured):
            protocol.official_score(predictions,out/'official_results.json')
        (out/'official_stdout.txt').write_text(captured.getvalue())
        official=read(out/'official_results.json')
        assert len(official['detailed_results'])==29
        rows=[]
        for tid in ids:
            entry=gt[tid]; candidates=[f for f in entry['failures'] if f['failure_id']==entry['root_cause']['failure_id']]
            assert len(candidates)==1
            g=candidates[0]; pred=predictions[tid]
            # Official Report carries the normalized category from untouched upstream.
            report=next(x for x in official['detailed_results'] if str(x['task_id'])==tid)
            true_category=int(report['gt_failure_case']); true_step=g['step_number']
            assert true_step==report['gt_step_number']
            distance=abs(pred['index']-true_step)
            rows.append({'task_id':tid,'steps':len(regenerated[tid]['steps']),
                         'predicted_step':pred['index'],'gold_step':true_step,
                         'predicted_category':pred['failure_case'],'gold_category':true_category,
                         'gold_failed_agent':g.get('failed_agent'),
                         'step_exact':distance==0,'category_exact':pred['failure_case']==true_category,
                         'joint_exact':distance==0 and pred['failure_case']==true_category,
                         'absolute_step_error':distance,
                         'predicted_step_in_range':1<=pred['index']<=len(regenerated[tid]['steps'])})
        N=len(rows); summ=official['summary']
        exact=sum(r['step_exact'] for r in rows); category=sum(r['category_exact'] for r in rows); joint=sum(r['joint_exact'] for r in rows)
        assert summ['Correct step number predictions']==exact
        assert summ['Correct cases']==category
        assert summ['Correct cases']+summ['Incorrect cases']==N
        assert summ['Correct step number predictions']+summ['Incorrect step number predictions']==N
        assert abs(summ['Overall average distance']-sum(r['absolute_step_error'] for r in rows)/N)<1e-12
        tolerances={str(k):sum(r['absolute_step_error']<=k for r in rows) for k in range(1,6)}
        for k,n in tolerances.items():assert abs(summ[f'Step accuracy within +-{k}']-n/N)<1e-12
        metrics={'n':N,'step_exact_count':exact,'step_exact_accuracy':exact/N,
                 'critical_category_count':category,'critical_category_accuracy':category/N,
                 'joint_step_category_count':joint,'joint_step_category_accuracy':joint/N,
                 'step_within_tolerance_counts':tolerances,'mean_absolute_step_error':summ['Overall average distance'],
                 'invalid_step_predictions':sum(not r['predicted_step_in_range'] for r in rows),
                 'valid_diagnostic_responses':N,'total_attempts':calls,'failed_attempts':failed_attempts,'usage_from_raw_cli_events':usage,
                 'note':'One run of a public 29-trajectory split. Joint is supplemental; not full AgentRx method or paper score replication.'}
        dump(out/'metrics.json',metrics); dump(out/'per_case.json',rows); dump(out/'call_audit.json',receipts)
        with (out/'per_case.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        # Gold and shifted-step negative controls invoke the same untouched official scorer.
        controls={}
        with tempfile.TemporaryDirectory(prefix='agentrx-scorer-controls-') as temp:
            for name,delta in [('gold_prediction',0),('all_steps_shifted_by_one',1)]:
                fake={r['task_id']:{'index':r['gold_step']+delta,'failure_case':r['gold_category'],'reason_for_failure':'CONTROL ONLY','reason_for_index':'CONTROL ONLY','taxonomy_checklist_reasoning':'CONTROL ONLY'} for r in rows}
                target=Path(temp)/f'{name}.json'
                with redirect_stdout(io.StringIO()):protocol.official_score(fake,target)
                s=read(target)['summary'];controls[name]={'step_exact':s['Correct step number predictions'],'category_exact':s['Correct cases']}
            assert controls['gold_prediction']=={'step_exact':29,'category_exact':29}
            assert controls['all_steps_shifted_by_one']=={'step_exact':0,'category_exact':29}
        dump(out/'scorer_controls.json',controls)
        acceptance={'status':'PASS','checked_at':now(),'scope':'Engineering execution and evidence validity; diagnosis accuracy reported separately',
                    'planned':29,'valid':29,'scored':29,'all_prompts_regenerated':True,'frozen_files_unchanged':True,
                    'official_scorer_preserved':True,'independent_arithmetic_matches':True,'negative_controls_passed':True,
                    'human_audit':'pending','plan_sha256':digest(ROOT/'plan.json'),
                    'evidence_hashes':{str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'calls').rglob('*')) if p.is_file()}}
        dump(out/'acceptance.json',acceptance)
        print(json.dumps({'status':'PASS',**metrics},ensure_ascii=False))
    except BaseException as exc:
        dump(out/'acceptance.json',{'status':'FAIL','checked_at':now(),'error':str(exc)})
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args();main(args.output)
