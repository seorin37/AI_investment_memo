import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel
from transformers import AutoModel
original = AutoModel.from_pretrained
def compatible_from_pretrained(*args, **kwargs):
    if "dtype" in kwargs:
        kwargs["torch_dtype"] = kwargs.pop("dtype")
    return original(*args, **kwargs)
AutoModel.from_pretrained = compatible_from_pretrained
print("CUDA 사용 가능:", torch.cuda.is_available())
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True, devices=["cuda:0"])
texts = [
    "삼성전자 HBM 공급 확대 여부 확인",
    "삼성전자 고대역폭 메모리 공급 확대 추진",
    "국내 항공사 국제선 운항 확대",
]
vectors = model.encode(
    texts, batch_size=1, max_length=256,
    return_dense=True, return_sparse=False, return_colbert_vecs=False
)["dense_vecs"]
vectors = np.asarray(vectors, dtype=np.float32)
vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)
scores = vectors[1:] @ vectors[0]
print("임베딩 차원:", vectors.shape[1])
for text, score in zip(texts[1:], scores):
    print(f"유사도 {float(score):.4f} | {text}")