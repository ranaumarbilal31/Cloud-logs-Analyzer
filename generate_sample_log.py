"""
generate_sample_log.py
Generates a realistic Apache Combined Log Format .log file for testing.
Usage: python generate_sample_log.py
Output: sample_access.log (5000 lines)
"""
import random
from datetime import datetime, timedelta

IPS = [f"192.168.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(50)]
IPS += ["10.0.0.1","172.16.0.5","203.0.113.42","198.51.100.7"]

PATHS = [
    "/", "/index.html", "/about", "/login", "/dashboard",
    "/api/users", "/api/data", "/static/main.css", "/static/app.js",
    "/favicon.ico", "/robots.txt", "/admin", "/uploads", "/logout",
    "/api/v1/logs", "/api/v1/analytics", "/profile", "/settings",
]

METHODS = ["GET","GET","GET","GET","POST","POST","PUT","DELETE"]

STATUSES = [
    200,200,200,200,200,200,200,200,
    201,204,
    301,302,304,
    400,401,403,404,404,404,
    500,502,503,
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'curl/7.88.1',
    'python-requests/2.31.0',
    'Go-http-client/1.1',
]

def gen_log(n=5000, output="sample_access.log"):
    start = datetime(2024, 11, 1, 0, 0, 0)
    with open(output, "w") as f:
        for i in range(n):
            ip = random.choice(IPS)
            ts = start + timedelta(seconds=random.randint(0, 86400*7))
            ts_str = ts.strftime('%d/%b/%Y:%H:%M:%S +0000')
            method = random.choice(METHODS)
            path = random.choice(PATHS)
            status = random.choice(STATUSES)
            size = random.randint(200, 15000)
            ua = random.choice(USER_AGENTS)
            line = f'{ip} - - [{ts_str}] "{method} {path} HTTP/1.1" {status} {size} "-" "{ua}"\n'
            f.write(line)
    print(f"✓ Generated {n} log lines → {output}")

if __name__ == "__main__":
    gen_log()
