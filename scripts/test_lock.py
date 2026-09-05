import asyncio, os, redis.asyncio as aioredis

async def main():
    rp = os.environ.get("REDIS_PASSWORD", "")
    r = aioredis.from_url("redis://redis:6379", password=rp, decode_responses=True)
    LUA = """
local val = redis.call('get', KEYS[1])
local now = tonumber(ARGV[4])
if not val then
    redis.call('set', KEYS[1], ARGV[1] .. ':' .. ARGV[2])
    redis.call('expire', KEYS[1], ARGV[3])
    return 1
end
return 0
"""
    await r.delete("gaking:test:lock:1")
    res = await r.eval(LUA, 1, "gaking:test:lock:1", "owner1", "1786708000", "10", "1786707900")
    print("eval result:", res)
    ttl = await r.ttl("gaking:test:lock:1")
    val = await r.get("gaking:test:lock:1")
    print("TTL:", ttl, "VALUE:", val)
    await r.delete("gaking:test:lock:1")
    await r.aclose()

asyncio.run(main())
