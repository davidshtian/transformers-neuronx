# Copyright Amazon Web Services and its Affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
from transformers_neuronx import dtypes
from transformers_neuronx import module
from transformers_neuronx import utils


class MixtralForCausalLM(module.PretrainedModel):

    def __init__(self, config):
        super().__init__()
        dtype, _, _ = utils.parse_amp(config.amp)
        dtype = dtypes.to_torch_dtype(dtype)
        self.model = MixtralModel(config)
        self.lm_head = module.LowMemoryLazyLinear(config.vocab_size, dtype=dtype, bias=False)

    def get_tied_parameters(self):
        return [(self.model.embed_tokens.weight, self.lm_head.weight)]

    def get_base_model(self):
        return self.model


class MixtralModel(module.LowMemoryModule):

    def __init__(self, config):
        super().__init__()
        self.embed_tokens = module.LowMemoryEmbedding(config.vocab_size, config.hidden_size)
        self.layers = module.LowMemoryModuleList([MixtralDecoderLayer(config) for _ in range(config.num_hidden_layers)])
        self.norm = MixtralRMSNorm(config)


class MixtralRMSNorm(module.LowMemoryModule):

    def __init__(self, config) -> None:
        super().__init__()
        self.weight = module.UninitializedParameter()


class MixtralDecoderLayer(module.LowMemoryModule):

    def __init__(self, config):
        super().__init__()
        self.self_attn = MixtralAttention(config)
        self.block_sparse_moe = MixtralSparseMoeBlock(config)
        self.input_layernorm = MixtralRMSNorm(config)
        self.post_attention_layernorm = MixtralRMSNorm(config)


class MixtralAttention(module.LowMemoryModule):

    def __init__(self, config):
        super().__init__()
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.head_dim = self.hidden_size // self.num_heads
        dtype, _, _ = utils.parse_amp(config.amp)
        dtype = dtypes.to_torch_dtype(dtype)
        self.q_proj = module.LowMemoryLazyLinear(self.num_heads * self.head_dim, bias=False, dtype=dtype)
        self.k_proj = module.LowMemoryLazyLinear(self.num_heads * self.head_dim, bias=False, dtype=dtype)
        self.v_proj = module.LowMemoryLazyLinear(self.num_heads * self.head_dim, bias=False, dtype=dtype)
        self.o_proj = module.LowMemoryLazyLinear(self.hidden_size, bias=False, dtype=dtype)


class MixtralBLockSparseTop2MLP(module.LowMemoryModule):

    def __init__(self, config):
        super().__init__()
        dtype, _, _ = utils.parse_amp(config.amp)
        dtype = dtypes.to_torch_dtype(dtype)
        self.w1 = module.LowMemoryLazyLinear(config.intermediate_size, bias=False, dtype=dtype)
        self.w2 = module.LowMemoryLazyLinear(config.intermediate_size, bias=False, dtype=dtype)
        self.w3 = module.LowMemoryLazyLinear(config.hidden_size, bias=False, dtype=dtype)


class MixtralSparseMoeBlock(module.LowMemoryModule):

    def __init__(self, config):
        super().__init__()
        dtype, _, _ = utils.parse_amp(config.amp)
        dtype = dtypes.to_torch_dtype(dtype)
        self.gate = module.LowMemoryLazyLinear(config.hidden_size, bias=False, dtype=dtype)
        self.experts = module.LowMemoryModuleList([MixtralBLockSparseTop2MLP(config) for _ in range(config.num_local_experts)])
