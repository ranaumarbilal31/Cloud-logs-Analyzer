"""
Pure-Python MapReduce Engine
Pipeline: Split → Map → Shuffle → Reduce
Uses multiprocessing.Pool for true parallel execution.
"""

import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# ─── Regex patterns ───────────────────────────────────────────────────────────
HTTP_STATUS_RE = re.compile(r'" (\d{3}) ')
HOUR_RE = re.compile(r'\[(\d{2}/\w+/\d{4}):(\d{2}):')
IP_RE = re.compile(r'^(\d{1,3}(?:\.\d{1,3}){3})')
METHOD_RE = re.compile(r'"(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)')


# ─── Map function (runs in worker process) ────────────────────────────────────
def map_chunk(lines):
    """
    Receives a list of log lines, emits (key, 1) pairs for:
      - HTTP status codes  → ("STATUS_404", 1)
      - Traffic hours      → ("HOUR_14",    1)
      - HTTP methods       → ("METHOD_GET", 1)
      - Unique IPs         → ("IP_count",   1)
    """
    intermediate = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # HTTP status
        m = HTTP_STATUS_RE.search(line)
        if m:
            intermediate.append((f"STATUS_{m.group(1)}", 1))

        # Hour
        m = HOUR_RE.search(line)
        if m:
            intermediate.append((f"HOUR_{m.group(2)}", 1))

        # Method
        m = METHOD_RE.search(line)
        if m:
            intermediate.append((f"METHOD_{m.group(1)}", 1))

        # IP
        m = IP_RE.match(line)
        if m:
            intermediate.append(("UNIQUE_IP", m.group(1)))

    return intermediate


# ─── Engine class ─────────────────────────────────────────────────────────────
class MapReduceEngine:

    def __init__(self, filepath: str, num_workers: int = None, chunk_lines: int = 500):
        self.filepath = filepath
        self.num_workers = num_workers or max(2, multiprocessing.cpu_count())
        self.chunk_lines = chunk_lines

    # ── SPLIT ──────────────────────────────────────────────────────────────────
    def split(self):
        """Divide file into equal-size line chunks."""
        chunks = []
        current = []
        with open(self.filepath, "r", errors="ignore") as f:
            for line in f:
                current.append(line)
                if len(current) >= self.chunk_lines:
                    chunks.append(current)
                    current = []
        if current:
            chunks.append(current)
        return chunks

    # ── MAP (parallel) ─────────────────────────────────────────────────────────
    def map_phase(self, chunks):
        """Submit each chunk to a worker process concurrently."""
        all_pairs = []
        # Use ThreadPoolExecutor on Railway (avoids fork issues in some envs)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {executor.submit(map_chunk, chunk): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                all_pairs.extend(future.result())
        return all_pairs

    # ── SHUFFLE & SORT ─────────────────────────────────────────────────────────
    def shuffle(self, pairs):
        """Group values by key."""
        grouped = defaultdict(list)
        for key, value in pairs:
            grouped[key].append(value)
        return dict(grouped)

    # ── REDUCE ─────────────────────────────────────────────────────────────────
    def reduce(self, grouped):
        """Aggregate grouped values into final counts / sets."""
        reduced = {}
        for key, values in grouped.items():
            if key == "UNIQUE_IP":
                reduced[key] = len(set(values))   # count distinct IPs
            else:
                reduced[key] = sum(values)         # sum counts
        return reduced

    # ── FULL PIPELINE ──────────────────────────────────────────────────────────
    def run(self):
        chunks = self.split()
        pairs = self.map_phase(chunks)
        grouped = self.shuffle(pairs)
        reduced = self.reduce(grouped)

        # ── Structure results for the dashboard ──────────────────────────────
        status_codes = {}
        hourly_traffic = {}
        methods = {}
        unique_ips = 0

        for key, val in reduced.items():
            if key.startswith("STATUS_"):
                status_codes[key[7:]] = val
            elif key.startswith("HOUR_"):
                hourly_traffic[key[5:]] = val
            elif key.startswith("METHOD_"):
                methods[key[7:]] = val
            elif key == "UNIQUE_IP":
                unique_ips = val

        # Sort
        status_codes = dict(sorted(status_codes.items(), key=lambda x: -x[1]))
        hourly_traffic = dict(sorted(hourly_traffic.items()))

        # Errors only (4xx, 5xx)
        errors = {k: v for k, v in status_codes.items() if k.startswith(("4", "5"))}
        total_requests = sum(status_codes.values())
        peak_hour = max(hourly_traffic, key=hourly_traffic.get) if hourly_traffic else "N/A"

        return {
            "status_codes": status_codes,
            "errors": errors,
            "hourly_traffic": hourly_traffic,
            "methods": methods,
            "unique_ips": unique_ips,
            "total_requests": total_requests,
            "peak_hour": peak_hour,
            "num_chunks": len(chunks),
            "num_workers": self.num_workers,
        }
