# Choosing a region and metric

## Hetzner Latency / CloudPingTest

Both sites run HTTP checks from the browser. Retrieve test URLs from the current
page or its scripts; a list of data centers alone does not identify test endpoints.
CloudPingTest also publishes its catalog and implementation in a public repository.
Replace the interface with curl timings or a Python client that uses timeouts,
checks HTTP status, and repeats requests from the same machine.

Distinguish DNS, connect, TLS, TTFB, and total time. Cumulative curl timings need
subtraction to obtain individual stage durations. Account for connection reuse,
caching, and the VPN/proxy route. Do not label HTTP total time as network RTT.

Implementation details verified on 2026-10-25; recheck them if the sites change:

- Sliplane computes `Math.round((performance.now()-start)/3.6)` and records the
  value in `fetch(...).finally(...)`, including failed requests. A table value
  does not confirm successful connectivity; it is a heuristic, not measured ICMP RTT.
- CloudPingTest uses `Image`, timing either onload **or onerror**, and marks a
  separate timeout as FAILED. Non-image responses explain onerror, but that
  handler alone does not distinguish them from network/TLS errors. Check endpoint
  availability separately before declaring the smallest number the winner.

When replacing this with Python, report explicit HTTP/TCP timings and errors
rather than reproducing the heuristic coefficient. Clearly identify methodology
differences when comparing with the original site.

## Ping-Admin

The free form lets users select nodes, including Russian cities; ping and
traceroute have separate forms. Read the protocol and current form fields before
starting. The documented API manages monitoring tasks and their statistics;
do not assume an anonymous API exists for the free one-off test itself.
Check-Host is a close automated alternative, but its probe locations and ASNs
may differ. If the request specifies a provider or city, ensure any substitution
still satisfies that requirement and explain the difference.

## Glassnode CEX

Use the map to shortlist server locations, then verify from the actual candidate
server against the required API. Capture the selected exchange, product,
endpoint, probe/region, Measured field, p50/other available metrics, and update
time. Do not turn missing values into zeroes; an empty table or pending rollups
cannot establish a ranking. State when data freshness is unspecified.

WS ping RTT, FIX logon/reject, and REST TTFB include different server-side work.
Do not compare them directly as interchangeable speed measurements. TCP/TLS to
a CDN measures the path to its edge, not necessarily to the exchange. A market
data response does not measure order execution. These numbers cannot establish
actual order-to-fill time.

At the verification date, the public REST API was advertised as a waitlist.
Check current documentation; do not invent an API or treat internal XHR endpoints
as a stable contract. Python can measure one accessible public endpoint;
reproducing the global map requires probes in the corresponding locations.

## Sources

- [Hetzner Latency](https://hetzner-latency.sliplane.io/)
- [CloudPingTest implementation](https://github.com/VarunAgw/CloudPingTest/blob/master/script.js)
- [CloudPingTest Hetzner regions](https://cloudpingtest.com/hetzner)
- [Ping-Admin form](https://ping-admin.com/free_test/) · [API](https://ping-admin.com/texts/134.html)
- [Glassnode CEX methodology and API](https://latency.glassnode.com/cex/about)
