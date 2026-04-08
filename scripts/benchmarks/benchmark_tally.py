import timeit
import random

# Mock 100,000 results
results = [
    {"highest_severity": random.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"])}
    for _ in range(100000)
]

def current_implementation():
    critical = sum(1 for r in results if r.get("highest_severity") == "CRITICAL")
    high = sum(1 for r in results if r.get("highest_severity") == "HIGH")
    return critical, high

def optimized_implementation():
    critical = 0
    high = 0
    for r in results:
        sev = r.get("highest_severity")
        if sev == "CRITICAL":
            critical += 1
        elif sev == "HIGH":
            high += 1
    return critical, high

if __name__ == "__main__":
    print("Benchmarking 100,000 records (100 iterations each):")
    t1 = timeit.timeit("current_implementation()", globals=globals(), number=100)
    print(f"Current O(2N) Multiple Passes: {t1:.4f} seconds")

    t2 = timeit.timeit("optimized_implementation()", globals=globals(), number=100)
    print(f"Optimized O(N) Single Pass:    {t2:.4f} seconds")
    print(f"Performance Gain: {(t1/t2 - 1)*100:.1f}% faster")
