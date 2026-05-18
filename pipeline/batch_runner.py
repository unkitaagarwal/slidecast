"""Run a slice of briefs.txt with N recipes processed concurrently.
Usage: python3 batch_runner.py <briefs_file> <start_idx> <count> [concurrency=5]"""
import sys, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Make .env available
def _load_env():
    env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)
_load_env()

sys.path.insert(0, os.path.dirname(__file__))
from run import run_one_recipe


def main():
    briefs_file = sys.argv[1]
    start = int(sys.argv[2])
    count = int(sys.argv[3])
    concurrency = int(sys.argv[4]) if len(sys.argv) > 4 else 5

    all_briefs = [l.strip() for l in open(briefs_file)
                  if l.strip() and not l.strip().startswith("#")]
    chunk = all_briefs[start:start + count]
    print(f"Processing {len(chunk)} briefs (idx {start}..{start+count-1}) "
          f"with concurrency={concurrency}")

    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(run_one_recipe, b): b for b in chunk}
        for f in as_completed(futures):
            b = futures[f]
            try:
                p = f.result()
                results[b] = p
                print(f"  DONE [{time.time()-t0:.1f}s] {b}")
            except Exception as e:
                print(f"  FAIL [{time.time()-t0:.1f}s] {b}: {e}")
                results[b] = None
    fails = [b for b, p in results.items() if p is None]
    print(f"\nBatch done in {time.time()-t0:.1f}s. {len(results)-len(fails)}/{len(results)} succeeded.")
    if fails:
        print("FAILED:")
        for b in fails:
            print(f"  - {b}")
        sys.exit(1)


if __name__ == "__main__":
    main()
