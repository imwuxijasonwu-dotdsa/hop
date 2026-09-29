"""Offline checks of ib_async 2.1.0 behaviours relied on by A v2.1 §8.6 / 03 §6.4 (no TWS/Gateway needed)."""
import asyncio, importlib.metadata as md, json
from ib_async import IB, Stock
from ib_async.ib import StartupFetchALL, StartupFetchNONE

FAKE_ACCOUNT = "DU0000000"  # synthetic placeholder, not a real account


def stub_connection(ib, calls):
    async def fake_connect(host, port, clientId, timeout):
        calls.append("client.connectAsync")
    ib.client.connectAsync = fake_connect
    ib.client.getAccounts = lambda: [FAKE_ACCOUNT]
    ib.client.isReady = lambda: True
    ib.client.serverVersion = lambda: 176
    ib.client.reqAutoOpenOrders = lambda *a: calls.append("reqAutoOpenOrders")
    for name in ["reqPositionsAsync", "reqOpenOrdersAsync", "reqCompletedOrdersAsync",
                 "reqAccountUpdatesAsync", "reqAccountUpdatesMultiAsync", "reqExecutionsAsync"]:
        def make(n):
            async def f(*a, **k):
                calls.append(n.replace("Async", ""))
                return []
            return f
        setattr(ib, name, make(name))


async def main():
    out = {"ib_async": md.version("ib_async")}

    # E7a: startup requests actually issued by IB.connectAsync
    for label, kw in [("defaults", {}),
                      ("readonly+StartupFetchNONE", {"readonly": True, "fetchFields": StartupFetchNONE})]:
        ib, calls = IB(), []
        stub_connection(ib, calls)
        await ib.connectAsync("127.0.0.1", 4002, clientId=321, **kw)
        out[f"E7a_startup_requests[{label}]"] = [c for c in calls if c != "client.connectAsync"]

    # E7b: reqHistoricalDataAsync timeout path
    ib, sent = IB(), []
    ib.client.isReady = lambda: True
    ib.client._reqIdSeq = 7
    ib.client.reqHistoricalData = lambda reqId, *a: sent.append(("reqHistoricalData", reqId))
    ib.client.cancelHistoricalData = lambda reqId: sent.append(("cancelHistoricalData", reqId))
    bars = await ib.reqHistoricalDataAsync(Stock("SYNTH", "SMART", "USD"), "", "1 D", "1 day",
                                           "TRADES", True, timeout=0.2)
    out["E7b_timeout"] = {"returned_type": type(bars).__name__, "returned_len": len(bars),
                          "raised": False, "client_calls": sent}

    # E7c: connectivity-restored (1102) hook and its removal
    for label, remove in [("default", False), ("errorEvent -= ib._onError", True)]:
        ib, hits = IB(), []
        async def fake_summary(*a, **k):
            hits.append("reqAccountSummary")
        ib.reqAccountSummaryAsync = fake_summary
        if remove:
            ib.errorEvent -= ib._onError
        ib.errorEvent.emit(-1, 1102, "Connectivity between IB and TWS has been restored", None)
        await asyncio.sleep(0.05)
        out[f"E7c_1102[{label}]"] = hits
    return out


res = asyncio.run(main())
print(json.dumps(res, indent=2))
