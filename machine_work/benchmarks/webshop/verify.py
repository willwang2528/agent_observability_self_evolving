"""Current offline verifier using the frozen WebShop action-serialization revision.

The copy of verify.py inside runner/ is archived with that revision. This entrypoint
uses the shared corrected verifier: human goal options are lists, whereas the
native purchased-options argument must be a dictionary. This fixture correction
changes no model prompts, actions, environment transitions or actual rewards.
"""
from pathlib import Path
import sys,importlib.util
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'runner'))
spec=importlib.util.spec_from_file_location('current_acceptance',HERE.parent/'_shared/verify.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
if __name__=='__main__':module.verify('webshop')
