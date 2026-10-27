import sys
from collections import Counter
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

files = sorted(Path(sys.argv[1]).glob("data/*.parquet"))
pf = pq.ParquetFile(files[0])
print("schema:")
for f in pf.schema_arrow:
    print(f"  {f.name}: {f.type}")
print("rows:", sum(pq.ParquetFile(p).metadata.num_rows for p in files))

sample = pf.read_row_group(0).slice(0, 3)
print("\nexamples (first 3 rows, truncated to 80 chars):")
for name in sample.column_names:
    vals = [str(v)[:80] for v in sample.column(name).to_pylist()]
    print(f"- {name}:")
    for v in vals:
        print(f"    {v!r}")

print("\nvalue notation (whole dataset):")
for col in ["sex", "age", "province", "district", "occupation"]:
    if col not in pf.schema_arrow.names:
        print(f"- {col}: (column missing)")
        continue
    c = Counter()
    for p in files:
        vc = pc.value_counts(pq.read_table(p, columns=[col]).column(col)).to_pylist()
        for d in vc:
            c[d["values"]] += d["counts"]
    print(f"- {col}: distinct={len(c)}, nulls={c.get(None, 0)}")
    if col == "age":
        nums = [k for k in c if isinstance(k, (int, float))]
        if nums:
            print(f"    min={min(nums)} max={max(nums)}")
    for k, n in c.most_common(12 if col != "district" else 8):
        print(f"    {k!r}: {n}")
