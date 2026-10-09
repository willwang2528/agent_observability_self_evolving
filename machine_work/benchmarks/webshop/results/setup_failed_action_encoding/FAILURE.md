# Invalid setup run; excluded from task success metrics

The initial runner discarded JSON search arguments, sending bare `search` to WebShop. This is a harness defect, not a valid model-performance measurement. Original calls and partial trajectory are retained. The same task indices and budgets are rerun after a versioned fix, without using gold. No low-reward valid rollout is retried.
