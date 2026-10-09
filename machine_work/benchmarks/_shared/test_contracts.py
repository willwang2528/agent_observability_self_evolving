import unittest
from contracts import actor_view, parse_action, validate_model_evidence

class ContractsTest(unittest.TestCase):
    def test_actor_gets_only_allowlisted_fields(self):
        inp={'observation':'table', 'available_actions':['look'], 'gold':'leak',
             'task':{'actions':['oracle']},'extra.expert_plan':['take apple']}
        self.assertEqual(actor_view(inp),{'observation':'table','available_actions':['look']})
    def test_tool_arguments_are_json_object(self):
        self.assertEqual(parse_action({'action':'get_user','arguments':'{"user_id":"u"}'}, True),
                         {'name':'get_user','kwargs':{'user_id':'u'}})
        for s in ['[]','null','not json']:
            with self.assertRaises(ValueError):parse_action({'action':'get_user','arguments':s},True)
    def test_no_shell_or_nested_actions(self):
        with self.assertRaises(ValueError):parse_action({'action':'','arguments':'{}'},True)
        with self.assertRaises(ValueError):parse_action({'action':['look'],'arguments':'{}'},False)
    def test_valid_raw_model_call(self):
        e=[{'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}},
           {'type':'item.completed','item':{'type':'agent_message','text':'{"action":"look","arguments":"{}"}'}}]
        self.assertTrue(validate_model_evidence(e,{'action':'look','arguments':'{}'}))
    def test_reject_no_call_and_fabricated_prediction(self):
        with self.assertRaises(ValueError):validate_model_evidence([],{'action':'look'})
        e=[{'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}},
           {'type':'item.completed','item':{'type':'agent_message','text':'{"action":"open","arguments":"{}"}'}}]
        with self.assertRaises(ValueError):validate_model_evidence(e,{'action':'look','arguments':'{}'})
    def test_reject_tool_contamination(self):
        e=[{'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}},
           {'type':'item.completed','item':{'type':'command_execution'}},
           {'type':'item.completed','item':{'type':'agent_message','text':'{"action":"look"}'}}]
        with self.assertRaises(ValueError):validate_model_evidence(e,{'action':'look'})

if __name__=='__main__':unittest.main()
