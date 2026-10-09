"""Prepare deterministic, label-independent Who&When pilot metadata from a fixed snapshot.

Only reads the downloaded JSON data. Does not execute upstream Python code.
"""
from __future__ import annotations
import collections
import hashlib
import json
import pathlib
import random
import re

ROOT = pathlib.Path(__file__).resolve().parent
SEED = 20261009

def write_json(name, value):
    (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def normalized_agent(value):
    value=str(value).strip()
    return 'Orchestrator' if re.fullmatch(r'Orchestrator(?:\s*\(.*\))?',value) else value

def main():
    records=[]
    for path in sorted((ROOT/'upstream'/'Who&When').glob('*/*.json')):
        raw=json.loads(path.read_text(encoding='utf-8'))
        stratum=path.parent.name
        history=raw['history']
        agent_key='name' if stratum=='Algorithm-Generated' else 'role'
        # Selection features are computed only from unlabeled input fields.
        record={
            'case_id':('algorithm_' if stratum=='Algorithm-Generated' else 'handcrafted_')+f'{int(path.stem):03d}',
            'source_path':str(path.relative_to(ROOT.parent)),
            'source_file':path.name,
            'stratum':stratum,
            'question_id':str(raw.get('question_ID') or hashlib.sha256(str(raw['question']).encode()).hexdigest()),
            'question_chars':len(str(raw['question'])),
            'history_chars':sum(len(str(entry.get('content','')))for entry in history),
            'steps':len(history),
            'agent_key':agent_key,
            'agents':sorted({str(entry.get(agent_key,'Unknown Agent'))for entry in history}),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        records.append(record)
    # Assign rank-based length tertiles separately within each source stratum.
    # This avoids overlap in tied lengths and never consults labels.
    rng=random.Random(SEED)
    selected=[]
    seen_question_ids=set()
    buckets={}
    for stratum in ['Algorithm-Generated','Hand-Crafted']:
        rows=sorted((r for r in records if r['stratum']==stratum),key=lambda r:(r['history_chars'],r['source_file']))
        n=len(rows)
        for i,label in enumerate(['short','medium','long']):
            bucket=rows[n*i//3:n*(i+1)//3]
            for row in bucket:row['length_tertile']=label
            buckets[f'{stratum}/{label}']={'n':len(bucket),'history_chars_min':min(r['history_chars']for r in bucket),'history_chars_max':max(r['history_chars']for r in bucket)}
            shuffled=list(bucket);rng.shuffle(shuffled)
            taken=[]
            for row in shuffled:
                if row['question_id'] not in seen_question_ids:
                    taken.append(row);seen_question_ids.add(row['question_id'])
                    if len(taken)==2:break
            assert len(taken)==2
            selected.extend(taken)
    assert len(selected)==12 and len(seen_question_ids)==12
    manifest={
        'dataset':'Who&When',
        'source_commit':'f4d2b6da464a826580e59b3a0eae15ea2d642d7c',
        'seed':SEED,
        'selection_policy':'For Algorithm-Generated then Hand-Crafted, sort by sum of history content character lengths (tie: source filename); split rank-based tertiles at floor(N*i/3); shuffle each bucket with shared random.Random(seed); take first two with globally unique question_ID. No label fields used.',
        'n_total':len(records),
        'n_selected':len(selected),
        'exclusions':'No label-quality exclusion. Duplicate question_ID skipped only to prevent same task appearing twice in pilot.',
        'buckets':buckets,
        'cases':selected,
    }
    write_json('selected_manifest.json',manifest)
    gold={}
    label_issues=[]
    annotation_key_hits=[]
    answer_substring_hits=[]
    raw_schemas=collections.Counter()
    history_schemas=collections.Counter()
    label_types=collections.Counter()
    qids=collections.Counter()
    missing=[]
    for row in records:
        raw=json.loads((ROOT.parent/row['source_path']).read_text(encoding='utf-8'))
        history=raw['history']; agentkey=row['agent_key']; step=int(raw['mistake_step'])
        raw_schemas[tuple(sorted(raw))]+=1
        label_types[type(raw['mistake_step']).__name__]+=1
        qids[row['question_id']]+=1
        for i,entry in enumerate(history):
            history_schemas[tuple(sorted(entry))]+=1
            if not isinstance(entry.get('content'),str) or not entry.get(agentkey):missing.append({'case_id':row['case_id'],'step':i})
        if not 0<=step<len(history):label_issues.append({'case_id':row['case_id'],'issue':'out_of_range_step','step':step,'steps':len(history)})
        else:
            step_agent=history[step].get(agentkey)
            if str(raw['mistake_agent'])!=str(step_agent):
                label_issues.append({'case_id':row['case_id'],'issue':'identity_mismatch_requiring_semantic_interpretation','label_agent':raw['mistake_agent'],'step':step,'history_agent':step_agent,'normalization_resolves':normalized_agent(raw['mistake_agent'])==normalized_agent(step_agent)})
        contents='\n'.join(str(e.get('content',''))for e in history)
        for key in ['mistake_agent','mistake_step','mistake_reason']:
            if key in contents:annotation_key_hits.append({'case_id':row['case_id'],'key':key})
        answer=str(raw.get('ground_truth','')).strip()
        if answer and answer.casefold()in contents.casefold():answer_substring_hits.append(row['case_id'])
        if row['case_id']in {r['case_id']for r in selected}:
            gold[row['case_id']]={'agent':str(raw['mistake_agent']),'step':step,'reason':str(raw['mistake_reason']),'raw_step':raw['mistake_step'],'normalized_agent':normalized_agent(raw['mistake_agent']),'history_agent_at_gold_step':history[step].get(agentkey)}
    write_json('gold.json',gold)
    write_json('inventory.json',{'cases':records})
    write_json('data_audit.json',{
        'n_records':len(records),'strata':dict(collections.Counter(r['stratum']for r in records)),
        'n_unique_question_ids':len(qids),'duplicate_question_id_groups':sum(n>1 for n in qids.values()),
        'selected_unique_question_ids':len(seen_question_ids),
        'raw_schema_variants':[{'keys':list(k),'n':v}for k,v in raw_schemas.items()],
        'history_schema_variants':[{'keys':list(k),'n':v}for k,v in history_schemas.items()],
        'mistake_step_raw_types':dict(label_types),'step_indexing':'zero-based as official utils enumerate(history)',
        'missing_content_or_agent':missing,
        'label_issues':label_issues,
        'label_issue_interpretation':'Agent identity differing from the actor at the labeled step is an audit flag requiring semantic interpretation, not proof of an invalid annotation. For example, an agent can be responsible for faulty code whose failure appears in a terminal response. Preserve original labels; do not automatically exclude or replace them.',
        'annotation_key_literal_hits_in_history':annotation_key_hits,
        'task_answer_literal_substring_in_history':{'n':len(answer_substring_hits),'case_ids':answer_substring_hits,'caveat':'Only an audit heuristic. Short numeric answers can occur coincidentally; not proof of annotation leakage. Original trajectory may legitimately contain the correct answer before failure.'},
        'model_input_policy':'Input is question plus optional system_prompt plus sanitized history content and agent identifiers. Top-level ground_truth, mistake_agent, mistake_step, mistake_reason, labels, is_correct and is_corrected are not sent. Sanitization is performed by the pilot harness and must be label independent.',
        'selection_uses_labels':False,
        'official_baseline_caveat':'Official inference/utils.py supplies task ground_truth answer in diagnostic prompts. Pilot omits it; answer-free diagnostic adaptation, not strict replication. Official evaluate.py uses substring matching; pilot should use strict equality after documented agent normalization.',
    })
    print(json.dumps({'selected':[{k:r[k]for k in ['case_id','stratum','length_tertile','history_chars','steps']}for r in selected],'gold_format':'top-level case_id -> {agent,step,reason,...}','raw_agent_label_differences':len(label_issues),'unresolved_after_normalization':sum(not r.get('normalization_resolves',True)for r in label_issues)},indent=2))
if __name__=='__main__':main()
