"""
AUTOMATED CONCURRENT LOAD TEST
Simulates concurrent users querying the health and API endpoints.
Run with: python tests/load_test.py
"""

import asyncio
import time
import httpx

TARGET_URL = "https://rti-website-sfpu.onrender.com"  # Replace with live backend URL
CONCURRENT_USERS = 25
TOTAL_REQUESTS = 100


async def send_request(client, request_id):
    start = time.time()
    try:
        response = await client.get(f"{TARGET_URL}/health")
        duration = round((time.time() - start) * 1000, 2)
        return {"id": request_id, "status": response.status_code, "ms": duration, "ok": response.status_code == 200}
    except Exception as e:
        duration = round((time.time() - start) * 1000, 2)
        return {"id": request_id, "status": 0, "ms": duration, "ok": False, "error": str(e)}


async def run_load_test():
    print(f"🚀 Starting Load Test on {TARGET_URL}...")
    print(f"📊 Concurrent Users: {CONCURRENT_USERS} | Total Requests: {TOTAL_REQUESTS}\n")

    start_time = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        semaphore = asyncio.Semaphore(CONCURRENT_USERS)

        async def worker(req_id):
            async with semaphore:
                return await send_request(client, req_id)

        tasks = [worker(i) for i in range(1, TOTAL_REQUESTS + 1)]
        results = await asyncio.gather(*tasks)

    total_time = round(time.time() - start_time, 2)
    successful = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    avg_latency = round(sum(r["ms"] for r in results) / len(results), 2) if results else 0

    print("=" * 50)
    print("📈 LOAD TEST RESULTS SUMMARY")
    print("=" * 50)
    print(f"✅ Successful Requests : {len(successful)} / {TOTAL_REQUESTS}")
    print(f"❌ Failed Requests     : {len(failed)}")
    print(f"⏱️  Total Duration     : {total_time} seconds")
    print(f"⚡ Average Latency     : {avg_latency} ms")
    print(f"🔄 Requests / Second   : {round(TOTAL_REQUESTS / total_time, 2)}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_load_test())