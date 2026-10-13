"""Negative controls: completion text alone and malformed streams must not pass."""
import json
import tempfile
import unittest
from pathlib import Path
from run import inspect_attempt, SCHEMA

class EventAuditTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.p=Path(self.tmp.name)
  self.response={k:'' for k in ['taxonomy_checklist_reasoning','reason_for_failure','reason_for_index']}
  self.response.update(failure_case=1,index=2)
  (self.p/'metadata.json').write_text(json.dumps({'exit_code':0,'timed_out':False}))
  (self.p/'response.json').write_text(json.dumps(self.response))
  self.events=[{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(self.response)}}, {'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':10}}]
 def tearDown(self): self.tmp.cleanup()
 def status(self):
  (self.p/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in self.events)+'\n')
  return inspect_attempt(self.p)
 def test_valid_stream(self): self.assertTrue(self.status()['usable'])
 def test_failure_event_vetoes_completed(self):
  self.events.append({'type':'turn.failed','error':{'message':'network'}})
  self.assertFalse(self.status()['usable'])
 def test_tool_contamination_rejected(self):
  self.events.append({'type':'item.completed','item':{'type':'command_execution'}})
  self.assertFalse(self.status()['usable'])
 def test_unknown_warning_rejected(self):
  self.events.append({'type':'item.completed','item':{'type':'error','message':'context truncated'}})
  self.assertFalse(self.status()['usable'])
 def test_tampered_response_rejected(self):
  (self.p/'response.json').write_text(json.dumps(dict(self.response,index=99)))
  self.assertFalse(self.status()['usable'])
 def test_malformed_event_rejected(self):
  self.status()
  with (self.p/'events.jsonl').open('a') as f:f.write('{invalid\n')
  self.assertFalse(inspect_attempt(self.p)['usable'])
 def test_no_usage_rejected(self):
  self.events[-1]['usage']={}
  self.assertFalse(self.status()['usable'])
if __name__=='__main__': unittest.main()
