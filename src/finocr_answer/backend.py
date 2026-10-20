"""Pinned b6500 execution condition; verify effective runtime, not README defaults."""
import re

EXECUTION = {'context':6144,'parallel':1,'batch':512,'ubatch':128,'threads':6,
             'flash_attention':'disabled','k_type':'f16','v_type':'f16','gpu_layers':'37/37',
             'device':'Vulkan0','gpu_name':'RTX 3070 Ti','cooperative_matrices':False}


def observe_settings(log: str) -> dict:
    def field(name):
        found=re.findall(r'\b'+re.escape(name)+r'\s*=\s*([^\r\n]+)',log)
        return found[-1].strip() if found else None
    declared=field('flash_attn')
    transitions=re.findall(r'Flash Attention was auto, set to (enabled|disabled)',log)
    return {'flash_attention_declared':declared,'flash_attention_effective':transitions[-1] if transitions else declared,
            'full_gpu_offload':bool(re.search(r'offloaded\s+37/37\s+layers',log)),
            'device': 'Vulkan0' if 'Vulkan0' in log else None,
            'gpu_name': 'RTX 3070 Ti' if 'RTX 3070 Ti' in log else None,
            'n_ctx':field('n_ctx'),'n_ctx_per_seq':field('n_ctx_per_seq'),'n_seq_max':field('n_seq_max'),
            'n_batch':field('n_batch'),'n_ubatch':field('n_ubatch'),
            'kv_f16':bool(re.search(r'K\s*\(f16\).*V\s*\(f16\)',log))}


def require_settings(log: str) -> dict:
    observed=observe_settings(log)
    expected={'flash_attention_declared':'disabled','flash_attention_effective':'disabled','full_gpu_offload':True,
              'device':'Vulkan0','gpu_name':'RTX 3070 Ti','n_ctx':'6144','n_ctx_per_seq':'6144',
              'n_seq_max':'1','n_batch':'512','n_ubatch':'128','kv_f16':True}
    bad={k:{'expected':v,'observed':observed[k]} for k,v in expected.items() if observed[k]!=v}
    if bad:raise ValueError(f'Effective backend condition differs; no inference submitted: {bad}')
    return observed
