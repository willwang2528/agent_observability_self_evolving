"""Regression checks: engineering completion cannot masquerade as task success."""
import copy,json,tempfile,unittest
from pathlib import Path
import verify

class SuccessGateTests(unittest.TestCase):
    def fixture(self):
        return {'integrity':'PASS','all_success':True,'successes':2,'cases':[{'task':i,'score':{'reward':1.0,'won':True,'done':True},'official_replay':'PASS','actor':{'calls':2}} for i in (0,1)]}
    def test_two_complete_verified_successes_pass(self):verify.success_gate(self.fixture())
    def test_partial_reward_fails_even_if_flags_claim_success(self):
        row=self.fixture();row['cases'][0]['score']['reward']=2/3
        with self.assertRaises(AssertionError):verify.success_gate(row)
    def test_zero_reward_fails(self):
        row=self.fixture();row['cases'][1]['score']={'reward':0,'won':False,'done':True}
        with self.assertRaises(AssertionError):verify.success_gate(row)
    def test_nonterminal_reward_fails(self):
        row=self.fixture();row['cases'][0]['score']['done']=False
        with self.assertRaises(AssertionError):verify.success_gate(row)
    def test_replacement_task_fails(self):
        row=self.fixture();row['cases'][0]['task']=2
        with self.assertRaises(AssertionError):verify.success_gate(row)
    def test_missing_real_call_fails(self):
        row=self.fixture();row['cases'][0]['actor']['calls']=0
        with self.assertRaises(AssertionError):verify.success_gate(row)
    def test_replay_failure_fails(self):
        row=self.fixture();row['cases'][0]['official_replay']='FAIL'
        with self.assertRaises(AssertionError):verify.success_gate(row)
    def test_model_prompt_has_only_observed_allowlist(self):
        observation=verify.actor_view({'observation':'visible','available_actions':['search'],'gold':'HIDDEN','task':{'reference':'SECRET'}})
        prompt=verify.prompt_for([],observation)
        self.assertNotIn('HIDDEN',prompt);self.assertNotIn('SECRET',prompt)
    def test_unverified_success_flag_fails(self):
        row=self.fixture();row['all_success']=False
        with self.assertRaises(AssertionError):verify.success_gate(row)

if __name__=='__main__':unittest.main()
