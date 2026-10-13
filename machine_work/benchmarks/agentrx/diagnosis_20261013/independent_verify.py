#!/usr/bin/env python3
"""Independent offline AgentRx audit. No project scorer/PASS or model calls.

The official IR module is imported directly. Official judge definitions are
executed as verbatim AST nodes with a local standard-library namespace, avoiding
provider initialization. Project protocol is used only for adversarial isolation
tests, never as the reference oracle or metric implementation.
"""
import argparse
import ast
import builtins
from collections import Counter
import contextlib
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
from statistics import mean, median, stdev, variance, multimode
import subprocess
import sys
import tempfile
from typing import List, Optional, Dict, Any

sys.dont_write_bytecode = True
DEFAULT_ROOT = Path('/Users/will/project/agent_observability_self_evolving/machine_work/benchmarks/agentrx/diagnosis_20261013')
COMMIT = '7a18c79708e7671be15124460f4f7296107c2a55'
PLAN_SHA = '53b506ed1bb5eba6328a2521472d587c9e40a896466b330e69d881ca79bb796f'
IDS = list(map(str, [2,3,4,12,20,21,28,31,32,34,38,39,41,47,55,59,63,71,72,74,79,80,82,87,91,98,99,104,105]))
PINNED = {
    'agentrx/ir/trajectory_ir.py': '99064b69825a8aeb5716298f48a053b1855b1ee9b0314324d85137462ef669a4',
    'agentrx/judge/judge.py': '9629515bc49fa83c686a2aa03343b4a5ee9ddc23215f4756f7767ee6c9a59323',
    'data/ground_truth/tau_ground_truth.json': '58067689b2ec42f9cbfec2a84ec08d39cea4d8270617b55d0185862753642d16',
    'data/tau_retail/tau_dataset_failed.json': '17f8b3356d1124274cc7ed0215b5ff696970073dbed57394c60e775d5f85d717',
}
KNOWN_WARNINGS = {
    'Under-development features enabled: skip_host_skill_discovery. Under-development features are incomplete and may behave unpredictably. To suppress this warning, set `suppress_unstable_features_warning = true` in /Users/will/.codex/config.toml.',
    'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.',
}
GOLD_CATEGORY_IDS = {
    'Instruction Adherence Failure':1, 'Invention of New Information':2,
    'Invalid Invocation':3, 'Misinterpretation of Tool Output':4,
    'Intent Plan Misalignment':5, 'Underspecified User Intent':6,
    'Intent Not Supported':7, 'Guardrails Triggered':8,
    'System Failure':9, 'Inconclusive':10,
}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def require(value, message):
    if not value: raise AssertionError(message)

def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def official_judge(path):
    names = {'TAXONOMY_DATA','_TMPL_NO_CONTEXT','_TMPL_WITH_CONTEXT','_TMPL_FAILURE',
             '_TMPL_VIOLATIONS_BEFORE','build_taxonomy_text','get_system_prompt',
             'FailureCase','Failure','Report','convert_to_failure_case',
             'load_failures_from_json','analysis'}
    selected = []
    for node in ast.parse(path.read_text(), filename=str(path)).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
            selected.append(node)
    found = {n.name for n in selected if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    found |= {t.id for n in selected if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name)}
    require(names == found, 'Missing official judge AST definitions')
    namespace = {k: globals()[k] for k in ['Enum','Counter','mean','median','stdev','variance','multimode',
                                         'List','Optional','Dict','Any','json','os','re','asdict','dataclass','datetime']}
    namespace.update(PROMPT_MODE='baseline', EXECUTION_MODE='violations-after')
    exec(compile(ast.Module(body=selected,type_ignores=[]), str(path),'exec'),namespace)
    return namespace, {getattr(n,'name',None) or n.targets[0].id:
                       hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in selected}

def verify_inputs(root, plan):
    upstream = root/'upstream'
    for rel, expected in PINNED.items(): require(sha(upstream/rel)==expected,'Pinned official source changed: '+rel)
    require(sha(root/'plan.json')==PLAN_SHA,'Plan changed after independent audit began')
    require(plan['source_commit']==COMMIT, 'Wrong source commit')
    for rel, expected in plan['frozen_files'].items():
        require(sha(root/rel)==expected,'Frozen artifact changed: '+rel)
    ir = import_file('independent_official_agentrx_ir',upstream/'agentrx/ir/trajectory_ir.py')
    j, ast_hashes = official_judge(upstream/'agentrx/judge/judge.py')
    raw_path = upstream/'data/tau_retail/tau_dataset_failed.json'
    raw = read(raw_path)
    trajectories = ir.tau_bench_ir(ir.load_trajectories(str(raw_path)))
    by_id = {t['trajectory_id']:t for t in trajectories}
    require(len(trajectories)==len(by_id)==29 and set(by_id)==set(IDS),'Official coverage differs from 29-case snapshot')
    require([x['task_id'] for x in plan['cases']]==IDS,'Frozen plan task list changed')
    require((root/'system_prompt.txt').read_text()==j['get_system_prompt'](),'Official baseline system prompt mismatch')
    for t, source in zip(trajectories,raw):
        tid=t['trajectory_id']; steps=t['steps']
        require(tid==str(source['task_id']),'Official input order mismatch')
        require([s['index'] for s in steps]==list(range(1,len(source['traj'])+1)),tid+': dropped/reindexed step')
        require(steps[0]['substeps'][0]['role']=='system',tid+': lost system policy')
        require(read(root/'inputs'/tid/'steps.json')==steps,tid+': official IR differs')
        expected='Conversation: '+str(steps)
        require((root/'inputs'/tid/'prompt.txt').read_text()==expected,tid+': official input differs')
        case=next(c for c in plan['cases'] if c['task_id']==tid)
        require(case['steps']==len(steps) and case['prompt_characters']==len(expected),tid+': wrong input metadata')
        require(sha(root/'inputs'/tid/'prompt.txt')==case['prompt_sha256'],tid+': wrong input hash')
    require(sum(len(t['steps']) for t in trajectories)==1064,'Incorrect complete-trace step count')

    # Adversarial checks against the actual input adapter, independent expected inputs.
    adapter=import_file('independently_tested_project_adapter',root/'protocol.py')
    changed=copy.deepcopy(raw)
    for row in changed:
        row['reward']='EXCLUDED_REWARD_SENTINEL'
        row['root_cause']={'failure_id':123456,'reason_for_root_cause':'EXCLUDED_GOLD_SENTINEL'}
        row['failures']=[{'step_number':123456,'failure_category':'EXCLUDED_CATEGORY_SENTINEL'}]
        row['info']['task']['instruction']='EXCLUDED_TASK_INSTRUCTION_SENTINEL'
        row['info']['task']['actions']=[{'EXCLUDED_ACTION_SENTINEL':True}]
        row['info']['task']['outputs']=['EXCLUDED_OUTPUT_SENTINEL']
        row['info']['reward_info']={'EXCLUDED_REWARD_INFO_SENTINEL':True}
    with tempfile.TemporaryDirectory(prefix='independent-agentrx-isolation-') as tmp:
        changed_path=Path(tmp)/'changed_wrapper.json'; changed_path.write_text(json.dumps(changed))
        original_open,original_io_open=builtins.open,io.open
        opened=[]
        def guarded_open(file,*args,**kwargs):
            if isinstance(file,(str,bytes,os.PathLike)):
                name=os.fsdecode(file);opened.append(name)
                require('ground_truth' not in name and 'tau_ground_truth' not in name,'Adapter opened diagnosis gold content')
            return original_open(file,*args,**kwargs)
        def guarded_io_open(file,*args,**kwargs):
            if isinstance(file,(str,bytes,os.PathLike)):
                name=os.fsdecode(file);opened.append(name)
                require('ground_truth' not in name and 'tau_ground_truth' not in name,'Adapter opened diagnosis gold content')
            return original_io_open(file,*args,**kwargs)
        try:
            builtins.open,io.open=guarded_open,guarded_io_open
            altered=adapter.build_inputs(changed_path,upstream)
        finally: builtins.open,io.open=original_open,original_io_open
        require(len(altered)==29,'Mutation changed coverage')
        for row in altered:
            require(row['user_prompt']=='Conversation: '+str(by_id[row['task_id']]['steps']),'Excluded gold/reference metadata affected input')
        changed[0]['traj'][0]['content']+=' INCLUDED_POLICY_SENTINEL'
        changed_path.write_text(json.dumps(changed))
        require('INCLUDED_POLICY_SENTINEL' in adapter.build_inputs(changed_path,upstream)[0]['user_prompt'],'Original policy excluded')
    return by_id,j,{'status':'PASS','frozen_files_checked':len(plan['frozen_files']),
                   'task_count':29,'total_steps':1064,'official_prompt_match':True,
                   'one_based_complete_steps':True,'gold_and_wrapper_mutation_independent':True,
                   'adapter_did_not_open_gold_content':True,'original_policy_retained':True,
                   'official_ast_sha256':ast_hashes,
                   'clarification':'Preparation hashes gold bytes for provenance; diagnostic labels do not enter model input.'}

def verify_command(command, root, attempt, plan):
    require(command[0]==plan['cli_binary']=='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex','Wrong CLI binary')
    def flag(key):
        require(command.count(key)==1,'Missing/duplicate command flag '+key)
        return command[command.index(key)+1]
    require(flag('--model')=='gpt-6-astra','Wrong configured model')
    require(flag('--sandbox')=='read-only','Wrong sandbox')
    require(Path(flag('--cd')).name.startswith('agentrx-isolated-'),'Unisolated working directory')
    require(Path(flag('--output-schema'))==root/'schema.json','Wrong schema source')
    require(Path(flag('--output-last-message'))==attempt/'response.json','Wrong response destination')
    for expected in ['--no-daemon','--ignore-user-config','--ephemeral','--skip-git-repo-check','--json']:
        require(command.count(expected)==1,'Missing isolation flag '+expected)
    config=[command[i+1] for i,x in enumerate(command) if x=='--config']
    require(len({x.split('=',1)[0] for x in config})==len(config),'Duplicate configuration override')
    required=['model_reasoning_effort="xhigh"',f'model_instructions_file="{root}/system_prompt.txt"',
              'web_search="disabled"','project_doc_max_bytes=0','memories.use_memories=false',
              'memories.generate_memories=false','features.memories=false','features.shell_tool=false',
              'features.unified_exec=false','features.multi_agent=false','features.apps=false',
              'features.plugins=false','features.remote_plugin=false','features.skill_search=false',
              'features.skip_host_skill_discovery=true','skills.include_instructions=false',
              'features.code_mode_host=false','features.computer_use=false','features.browser_use=false',
              'features.browser_use_external=false','features.in_app_browser=false','features.image_generation=false',
              'features.hooks=false','features.goals=false']
    require(set(required)<=set(config),'Missing expected runtime isolation config')
    require(command[-1]=='-','Prompt not read from stdin')

def inspect_raw_attempt(root, attempt, plan, case):
    meta=read(attempt/'metadata.json')
    require(meta['task_id']==case['task_id'],'Attempt task ID mismatch')
    require(meta['plan_sha256']==PLAN_SHA,'Attempt ran against different plan')
    require(meta['prompt_sha256']==case['prompt_sha256'],'Attempt input hash mismatch')
    verify_command(meta['command'],root,attempt,plan)
    events=[]; parse_errors=[]
    for n,line in enumerate((attempt/'events.jsonl').read_text().splitlines(),1):
        try: events.append(json.loads(line))
        except ValueError: parse_errors.append(n)
    errors=[]; tools=[]; warnings=[]; finals=[]; completed=[]
    allowed={'thread.started','turn.started','turn.completed','item.started','item.updated','item.completed','turn.failed','error'}
    for event in events:
        kind=event.get('type')
        if kind not in allowed: errors.append({'unknown_event':kind})
        if kind in {'turn.failed','error'}: errors.append(event)
        if kind=='turn.completed': completed.append(event)
        if kind in {'item.started','item.updated','item.completed'}:
            item=event['item'];typ=item['type']
            if typ=='error':
                if item.get('message') in KNOWN_WARNINGS: warnings.append(item['message'])
                else: errors.append(event)
            elif typ not in {'agent_message','reasoning'}: tools.append(typ)
            if kind=='item.completed' and typ=='agent_message': finals.append(item.get('text',''))
    require(not tools,'Tool contamination in any attempt: '+str(attempt))
    prediction=None; prediction_error=None
    try:
        prediction=read(attempt/'response.json')
        expected={'taxonomy_checklist_reasoning','reason_for_failure','reason_for_index','failure_case','index'}
        require(isinstance(prediction,dict) and set(prediction)==expected,'Wrong output fields')
        require(type(prediction['failure_case']) is int and 0<=prediction['failure_case']<=10,'Invalid raw category type/range')
        require(type(prediction['index']) is int,'Invalid raw index type')
        for key in expected-{'failure_case','index'}: require(isinstance(prediction[key],str),'Invalid rationale type')
        require(len(finals)==1 and json.loads(finals[0])==prediction,'Raw completion differs from scored JSON')
    except Exception as exc: prediction_error=str(exc)
    usage={k:sum(e.get('usage',{}).get(k,0) for e in completed) for k in ['input_tokens','cached_input_tokens','output_tokens']}
    valid=(meta['exit_code']==0 and not meta['timed_out'] and len(completed)==1 and not errors and not parse_errors
           and prediction_error is None and usage['input_tokens']>0 and usage['output_tokens']>0)
    return {'task_id':case['task_id'],'attempt':attempt.name,'valid':valid,'unfinished':meta['exit_code'] is None,
            'exit_code':meta['exit_code'],'timed_out':meta['timed_out'],'completion_count':len(completed),
            'parse_errors':parse_errors,'errors':errors,'tool_items':tools,'known_warnings':sorted(set(warnings)),
            'prediction_error':prediction_error,'usage':usage,'prediction':prediction,
            'evidence_hashes':{p.name:sha(p) for p in sorted(attempt.iterdir()) if p.is_file() and p.name!='validation.json'}}

def score_independently(root, by_id, j, predictions):
    # Direct official functions, never protocol.official_score or score.py.
    with contextlib.redirect_stdout(io.StringIO()):
        labels=j['load_failures_from_json'](str(root/'upstream/data/ground_truth/tau_ground_truth.json'))
    require(len(labels)==29 and {str(x.task_id) for x in labels}==set(IDS),'Official labels missing/duplicated')
    raw_gold={str(g['trajectory_id']):g for g in read(root/'upstream/data/ground_truth/tau_ground_truth.json')}
    rows=[];reports=[]
    for gold in labels:
        tid=str(gold.task_id);p=predictions[tid];entry=raw_gold[tid]
        matching=[f for f in entry['failures'] if f['failure_id']==entry['root_cause']['failure_id']]
        require(len(matching)==1 and gold.step_number==matching[0]['step_number'],'Wrong root-cause resolution')
        manual_gold_category=GOLD_CATEGORY_IDS[matching[0]['failure_category']]
        require(gold.failure_case.value==manual_gold_category,'Wrong gold category resolution')
        r=j['Report'](tid,len(by_id[tid]['steps']))
        r.add_failure(j['Failure'](tid,p['failure_case'],p['reason_for_failure'],p['index'],p['taxonomy_checklist_reasoning']))
        r.compute_stats(gold);reports.append(r.to_dict())
        distance=abs(p['index']-gold.step_number)
        rows.append({'task_id':tid,'predicted_step':p['index'],'gold_step':gold.step_number,
                     'predicted_category':p['failure_case'],'gold_category':gold.failure_case.value,
                     'steps':len(by_id[tid]['steps']),'category_correct':p['failure_case']==gold.failure_case.value,
                     'step_correct':distance==0,'joint_correct':distance==0 and p['failure_case']==gold.failure_case.value,
                     'absolute_step_error':distance,'predicted_step_in_range':1<=p['index']<=len(by_id[tid]['steps'])})
    with tempfile.TemporaryDirectory(prefix='independent-agentrx-official-score-') as tmp:
        target=Path(tmp)/'official.json'
        with contextlib.redirect_stdout(io.StringIO()): j['analysis'](reports,str(target),'gpt-6-astra','codex-exec')
        official=read(target)
    s=official['summary'];n=29
    cat=sum(r['category_correct'] for r in rows);step=sum(r['step_correct'] for r in rows);joint=sum(r['joint_correct'] for r in rows)
    mae=sum(r['absolute_step_error'] for r in rows)/n
    norm=sum(r['absolute_step_error']/r['steps'] for r in rows)/n
    require(len(official['detailed_results'])==n,'Official scorer dropped reports')
    require(s['Correct cases']==cat and s['Correct cases']+s['Incorrect cases']==n,'Category denominator mismatch')
    require(s['Correct step number predictions']==step and s['Incorrect step number predictions']+step==n,'Step denominator mismatch')
    require(abs(s['Overall average distance']-mae)<1e-12,'MAE mismatch')
    require(abs(s['Normalized overall average distance']-norm)<1e-12,'Normalized MAE mismatch')
    tolerances={str(k):sum(r['absolute_step_error']<=k for r in rows) for k in range(1,6)}
    for k,v in tolerances.items():require(abs(s[f'Step accuracy within +-{k}']-v/n)<1e-12,'Tolerance mismatch')
    metrics={'denominator':n,'category_correct':cat,'category_accuracy':cat/n,'step_correct':step,'step_accuracy':step/n,
             'joint_correct_supplemental':joint,'joint_accuracy_supplemental':joint/n,'step_tolerance_counts':tolerances,
             'mean_absolute_step_error':mae,'normalized_mean_absolute_step_error':norm,
             'out_of_range_predictions':sum(not r['predicted_step_in_range'] for r in rows)}
    return metrics,rows,official

def official_controls(j):
    """Synthetic metric controls, explicitly separate from any model evidence."""
    results={}
    with tempfile.TemporaryDirectory(prefix='independent-agentrx-controls-') as tmp:
        for name,category,step in [('exact',4,7),('step_plus_one',4,8),('wrong_category',5,7),('both_wrong',5,8)]:
            report=j['Report']('CONTROL_ONLY',10)
            report.add_failure(j['Failure']('CONTROL_ONLY',category,'Synthetic scorer control',step))
            report.compute_stats(j['Failure']('CONTROL_ONLY',4,'Synthetic gold',7))
            destination=Path(tmp)/(name+'.json')
            with contextlib.redirect_stdout(io.StringIO()):j['analysis']([report.to_dict()],str(destination),'CONTROL_ONLY','none')
            s=read(destination)['summary']
            require(s['Correct cases']==int(category==4),'Official category control failed')
            require(s['Correct step number predictions']==int(step==7),'Official exact-step control failed')
            require(s['Step accuracy within +-1']==1,'Official tolerance control failed')
            require(s['Overall average distance']==abs(step-7),'Official distance control failed')
            require(s['Normalized overall average distance']==abs(step-7)/10,'Official normalized control failed')
            results[name]={'category_correct':s['Correct cases'],'step_correct':s['Correct step number predictions'],
                           'absolute_distance':s['Overall average distance'],'synthetic_not_model_result':True}
    return results

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-dir','--root',dest='root',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--output-prefix',type=Path,default=Path('/tmp/agentrx_independent_audit_20261013'))
    parser.add_argument('--static-only',action='store_true');args=parser.parse_args();root=args.root.resolve()
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'RUNNING','run_root':str(root),
            'source_commit':COMMIT,'plan_sha256':PLAN_SHA,'model_calls_in_this_audit':0,
            'scope':'All 29 tau traces in the pinned public GitHub snapshot; not the latest-paper 39 tau or entire 170-case collection.',
            'method_scope':'Official baseline prompt and IR via Codex model transport; no invariant pipeline or self-evolution result.',
            'human_audit':'pending','independent_of_project_scorer':True,
            'runtime_identity_boundary':'CLI command proves requested model/effort; provider-internal model identity is not independently attested.'}
    exit_code=0
    try:
        plan=read(root/'plan.json');by_id,j,static=verify_inputs(root,plan);report['static']=static
        report['synthetic_official_metric_controls']=official_controls(j)
        repository=root.parents[3]
        if (repository/'.git').exists():
            protected=['machine_work/benchmarks/'+name for name in ['who_when','alfworld','webshop','tau_bench','_shared']]
            delta=subprocess.run(['git','diff','--name-only','HEAD','--',*protected],cwd=repository,capture_output=True,text=True,check=True)
            require(not delta.stdout.strip(),'Previously tracked benchmark files modified: '+delta.stdout)
            report['legacy_tracked_benchmarks_unchanged_from_head']=True
            report['repository_head_at_audit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
        require(plan['model']=='gpt-6-astra' and plan['reasoning_effort']=='xhigh','Wrong planned model')
        require(plan['max_attempts']==2 and plan['workers']==3 and plan['timeout_seconds']==600,'Execution budget changed')
        if args.static_only: report['status']='STATIC_PASS_RUN_NOT_YET_ACCEPTED'
        else:
            receipts=[];predictions={};missing=[]
            for case in plan['cases']:
                tid=case['task_id'];attempts=sorted((root/'calls'/tid).glob('attempt_*'))
                require(len(attempts)<=2,tid+': unplanned retry')
                valid=[]
                for attempt in attempts:
                    receipt=inspect_raw_attempt(root,attempt,plan,case);receipts.append(receipt)
                    if receipt['valid']:valid.append(receipt)
                if not valid:missing.append(tid);continue
                require(len(valid)==1 and valid[0]['attempt']==attempts[-1].name,tid+': success-conditioned retries/selection')
                predictions[tid]=valid[0]['prediction']
            report['attempts']=receipts;report['planned_cases']=29;report['completed_valid_cases']=len(predictions)
            report['total_attempts']=len(receipts);report['missing_or_incomplete_cases']=missing
            report['failed_attempts']=[{'task_id':r['task_id'],'attempt':r['attempt']} for r in receipts if not r['valid']]
            report['usage']={k:sum(r['usage'][k] for r in receipts) for k in ['input_tokens','cached_input_tokens','output_tokens']}
            if missing:report['status']='INCOMPLETE';exit_code=2
            else:
                metrics,rows,official=score_independently(root,by_id,j,predictions)
                report['diagnosis_metrics']=metrics;report['per_case']=rows;report['official_recomputed_summary']=official['summary']
                published=root/'evaluation/official_results.json'
                if published.exists():
                    original=read(published)
                    require(original['summary']==official['summary'],'Project summary differs from direct official recomputation')
                    require(original['detailed_results']==official['detailed_results'],'Project per-case reports differ from direct official recomputation')
                    report['project_metric_comparison']='MATCH'
                else:report['project_metric_comparison']='NOT_YET_WRITTEN'
                report['status']='PASS_EXECUTION_AND_OFFICIAL_SCORING'
    except Exception as exc:
        report['status']='FAIL';report['error']=f'{type(exc).__name__}: {exc}';exit_code=1
    args.output_prefix.parent.mkdir(parents=True,exist_ok=True)
    args.output_prefix.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    text=['# AgentRx independent audit','',f"Status: **{report['status']}**",'',report['scope'],'',report['method_scope'],'',
          'Independent audit performs no model calls and does not trust project PASS summaries. Human audit remains pending.','']
    if 'static' in report:text += [f"Static checks: {report['static']['status']}; 29 complete trajectories, 1,064 original steps; official prompt, IR, immutable hashes and isolation controls verified.",'']
    if 'diagnosis_metrics' in report:
        m=report['diagnosis_metrics'];text += [f"Category: {m['category_correct']}/29; exact step: {m['step_correct']}/29; supplemental joint: {m['joint_correct_supplemental']}/29.",
          f"MAE: {m['mean_absolute_step_error']}; normalized MAE: {m['normalized_mean_absolute_step_error']}.",
          f"Real diagnostic attempts: {report['total_attempts']}; valid cases: {report['completed_valid_cases']}/29; tool contamination: none.",'',
          f"Out-of-range diagnostic indices retained as errors: {m['out_of_range_predictions']}. Valid calls/JSON responses do not imply a valid localized step for every case.",'',
          'Execution/scoring completion is reported independently from prediction correctness. Wrong predictions remain in the 29-case denominator.','']
    if report.get('error'):text += ['Failure: '+report['error'],'']
    text += ['Runtime evidence establishes the configured gpt-6-astra/xhigh request; provider-internal identity is not independently attested.',
             'Preparation reads gold bytes only to record their checksum; gold labels are used for offline scoring and are absent from diagnostic inputs.',
             'Category 0 and out-of-range integer indices, if emitted, are retained as wrong predictions according to the frozen protocol; they are not grounds for accuracy-conditioned retries.','']
    args.output_prefix.with_suffix('.md').write_text('\n'.join(text))
    print(json.dumps({k:report[k] for k in ['status','completed_valid_cases','total_attempts','diagnosis_metrics','error'] if k in report},ensure_ascii=False))
    return exit_code

if __name__=='__main__': raise SystemExit(main())
