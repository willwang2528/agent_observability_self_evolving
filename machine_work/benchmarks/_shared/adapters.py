"""Thin adapters: official state transitions and official rewards are retained."""
from pathlib import Path
import os, sys, random, json
ROOT=Path(__file__).resolve().parents[3]
CACHE=ROOT/'.benchmark_cache'

def setup_imports():
    os.environ['ALFWORLD_DATA']=str(CACHE/'alfworld_data')
    for name in ('alfworld','webshop','tau_bench'):sys.path.insert(0,str(CACHE/name))

def alf_env(game,expert=False):
    setup_imports()
    import textworld
    from alfworld.agents.environment.alfred_tw_env import AlfredDemangler,AlfredInfos,AlfredExpert
    wrappers=[AlfredDemangler(shuffle=False),AlfredInfos]
    if expert:wrappers.append(AlfredExpert(expert_type='handcoded'))
    return textworld.start(str(CACHE/'alfworld_data'/game),
        request_infos=textworld.EnvInfos(won=True,admissible_commands=True),wrappers=wrappers)

class AlfWorld:
    tools=False
    rules='Complete the household task. Choose one exact available action each turn. Search receptacles systematically; remember observed objects and appliance state. No expert plan is available.'
    def __init__(self,task,user=None):self.env=alf_env(task);self.state=self.env.reset()
    def view(self):return {'observation':self.state.feedback,'available_actions':self.state.admissible_commands}
    def step(self,action):
        self.state,reward,done=self.env.step(action)
        return {'observation':self.state.feedback,'reward':float(reward),'done':bool(done),'won':bool(self.state['won'])}
    def score(self):return {'reward':float(self.state['won']),'won':bool(self.state['won'])}
    def close(self):self.env.close()

class WebShop:
    tools=False
    rules='Purchase a product matching the instruction. Actions: search[keywords] or click[exact available clickable]. Inspect features/description and choose required options before click[buy now]. Buy Now is a simulated purchase in this benchmark. You have no access to hidden goal metadata.'
    def __init__(self,task,user=None):
        setup_imports();random.seed(20261009)
        from web_agent_site.envs import WebAgentTextEnv
        self.env=WebAgentTextEnv(observation_mode='text',num_products=1000,human_goals=True)
        self.observation,_=self.env.reset(session=int(task));self.reward=0;self.done=False
    def view(self):return {'observation':self.observation,'available_actions':self.env.get_available_actions()}
    def step(self,action):
        self.observation,self.reward,self.done,_=self.env.step(action)
        return {'observation':self.observation,'reward':float(self.reward),'done':bool(self.done)}
    def score(self):return {'reward':float(self.reward),'won':self.reward==1.0,'done':bool(self.done)}
    def close(self):self.env.close()

class ReplayUser:
    def __init__(self,opening='',replies=None):self.opening=opening;self.replies=iter(replies or [])
    def reset(self,instruction=None):return self.opening
    def step(self,content):return next(self.replies,'###STOP###')
    def get_total_cost(self):return 0.0

class CodexUser:
    """Official llm simulator prompt and dialogue protocol; only its model transport changes."""
    def __init__(self,directory):self.directory=Path(directory);self.messages=[];self.index=0
    def generate(self):
        from model import call_model
        pred=call_model('Simulate the user. Put your one-line reply in action and {} in arguments.\n'+json.dumps(self.messages,ensure_ascii=False),self.directory/f'{self.index:03d}')
        self.index+=1;reply=pred['action'];self.messages.append({'role':'assistant','content':reply});return reply
    def reset(self,instruction=None):
        from tau_bench.envs.user import LLMUserSimulationEnv
        system=LLMUserSimulationEnv.build_system_prompt(self,instruction)
        self.messages=[{'role':'system','content':system},{'role':'user','content':'Hi! How can I help you today?'}]
        return self.generate()
    def step(self,content):self.messages.append({'role':'user','content':content});return self.generate()
    def get_total_cost(self):return 0.0 # dollars unknown under subscription; usage is retained per actual call

class TauBench:
    tools=True
    def __init__(self,task,user=None):
        setup_imports()
        from tau_bench.envs.retail.env import MockRetailDomainEnv
        self.env=MockRetailDomainEnv(user_strategy='human',task_split='test',task_index=int(task))
        self.env.user=user or ReplayUser();r=self.env.reset(int(task));self.observation=r.observation
        self.rules=self.env.wiki+'\n\n'+json.dumps(self.env.rules)+'\nTools:\n'+json.dumps(self.env.tools_info)+ '\nUse respond with {"content":"..."} to speak to the user. Return one action at a time.'
        self.done=False;self.reward_info=None;self.last_hash=self.env.get_data_hash()
    def view(self):return {'observation':self.observation,'available_actions':[x['function']['name'] for x in self.env.tools_info]+['respond']}
    def step(self,action):
        from tau_bench.types import Action
        self.last_hash=self.env.get_data_hash()
        r=self.env.step(Action(**action));self.observation=r.observation;self.done=r.done
        if r.info.reward_info:self.reward_info=r.info.reward_info.model_dump()
        return {'observation':r.observation,'reward':float(r.reward),'done':bool(r.done),
                'source':r.info.source,'db_hash':self.last_hash if r.done else self.env.get_data_hash()}
    def score(self):
        # Official scorer mutates env.data and actions while constructing reference state.
        # Invoke once at termination and preserve the full official result separately from actor input.
        if self.reward_info is None:self.reward_info=self.env.calculate_reward().model_dump()
        return {'reward':float(self.reward_info['reward']),'won':self.reward_info['reward']==1.0,'done':self.done,'official':self.reward_info}
    def close(self):pass

ADAPTERS={'alfworld':AlfWorld,'webshop':WebShop,'tau_bench':TauBench}
