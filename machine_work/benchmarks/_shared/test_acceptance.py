"""Adversarial checks against raw evidence; neither installs nor calls a model."""
import unittest,tempfile,json,shutil
from pathlib import Path
from verify import check_calls
from adapters import ROOT

class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        src=ROOT/'machine_work/benchmarks/alfworld/results/run_20261009/case_000/actor_calls/000'
        shutil.copytree(src,self.root/'000')
    def tearDown(self):self.tmp.cleanup()
    def test_real_saved_call_is_accepted(self):self.assertEqual(check_calls(self.root)['calls'],1)
    def test_forged_prediction_is_rejected(self):
        p=self.root/'000/prediction.json';x=json.loads(p.read_text());x['action']='forged';p.write_text(json.dumps(x))
        with self.assertRaises(ValueError):check_calls(self.root)
    def test_missing_completion_is_rejected(self):
        p=self.root/'000/events.jsonl';events=[json.loads(s) for s in p.read_text().splitlines()]
        p.write_text('\n'.join(json.dumps(e) for e in events if e.get('type')!='turn.completed'))
        with self.assertRaises(ValueError):check_calls(self.root)
    def test_zero_usage_is_rejected(self):
        p=self.root/'000/events.jsonl';events=[json.loads(s) for s in p.read_text().splitlines()]
        for e in events:
            if e.get('type')=='turn.completed':e['usage']={'input_tokens':0,'output_tokens':0}
        p.write_text('\n'.join(json.dumps(e) for e in events))
        with self.assertRaises(ValueError):check_calls(self.root)
    def test_unexpected_error_item_is_rejected(self):
        p=self.root/'000/events.jsonl';p.write_text(p.read_text()+'\n'+json.dumps({'type':'item.completed','item':{'type':'error','message':'unexpected transport warning'}})+'\n')
        with self.assertRaises(AssertionError):check_calls(self.root)
if __name__=='__main__':unittest.main()
