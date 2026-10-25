---
name: network-check
description: >-
  Check certificates and subdomains through CT, website availability across
  countries, and latency to cloud regions and public exchange APIs. Choose
  between local ping/curl/dig, crt.sh and Check-Host APIs, Ping-Admin, Hetzner
  Latency, CloudPingTest, and Glassnode CEX. Use for "check availability from
  different countries", "find subdomains in certificates", or "compare latency
  to regions or exchanges". Covers diagnostics and measurement selection,
  not network configuration or trading.
---

# Network checks

Identify the target and **measurement origin**: the current machine/browser,
the user's server, or external probes. These origins answer different questions.
Use the model to select checks and interpret results; obtain current certificates,
availability, and latency through tools rather than model memory.

## Website replacement levels

- **A — local tools:** replace calculations or measurements from the same machine.
- **B — external API:** replaces the web interface, but still depends on the service's data or probes.
- **C — live page:** current records, methodology, or service results require live retrieval; a browser can automate reading them.

| Resource | What it provides | Interface replacement | Data to retrieve from the site or API |
| --- | --- | --- | --- |
| crt.sh | Published certificates, names/SANs, and candidate subdomains | **B:** JSON → Python/jq for filtering and deduplication; openssl checks only a particular server's certificate | CT records: ID, names, issuer, validity, publication time; a local TLS request cannot replace the CT database |
| check-host.net | HTTP, ping, DNS, TCP/UDP checks from several countries | **B:** API and bundled Python client; local curl/dig/ping cover only one observation point | Current probes, country/city/ASN, request_id, each probe's result, and report link |
| hetzner-latency.sliplane.io | Approximate comparison of Hetzner regions from a browser | **A:** curl/Python with an explicit metric against the same endpoints; **C:** current regions and methodology | Endpoint and region code, mean/median/min/max/latest, measurement time and origin; this is not ICMP ping |
| ping-admin.com/free_test/ | One-off external checks, including selection of Russian cities; separate ping/traceroute forms | **C:** browser; **B:** Check-Host covers a similar task with different probes | Selected probes, protocol, timing/status/error, and available result details; do not treat the monitoring API as the free form's API |
| cloudpingtest.com | Browser-based comparison of cloud providers' regions | **A:** curl/Python against current endpoints; **C:** provider/region catalog and measurement code | Provider, region, test URL, samples, mean/median/min/max, errors, and methodology |
| latency.glassnode.com/cex | External probe latency to public exchange APIs by product and protocol | **C:** live table; a custom WS/REST/FIX client reproduces one origin, while a distributed network requires multiple servers | Exchange, product, endpoint, measurement type, probe/region, p50 and other displayed percentiles, timestamps, and missing data |

## Workflow

1. Choose the smallest check that answers the question. For HTTP, use the actual
   URL; for TCP, the port; for DNS, the record type; for an exchange, the required
   product and protocol. Prefer existing curl, dig, ping, mtr/traceroute, and
   openssl tools; installing another tool is usually unnecessary.
2. Send external services only public targets without tokens or private URLs.
   Preserve the existing VPN, proxy, and kill switch. Label measurements routed
   through a VPN; do not disable protection to obtain a "clean ping".
3. For CT and Check-Host, read the [API contracts](references/api.md). Check-Host client:
   `python3 "${CLAUDE_SKILL_DIR}/scripts/check_host.py" http https://example.com --max-nodes 3`.
   For specific locations, retrieve the current node list first and pass
   `--node <hostname>` for each selected node. Do not hard-code stale node names.
4. For clouds and exchanges, read the [methodology and limitations](references/latency.md).
   A browser on the agent's machine is not the user's browser. Measure from the
   machine for which the region is being selected; state the limitation if that
   machine is unavailable.
5. Compare the same metrics over the same route. Report successful samples,
   errors, median, and spread. Keep ICMP, TCP, TLS, HTTP TTFB, full response time,
   and WS RTT separate. A few repeats suffice for an initial comparison;
   a stability claim requires an appropriate observation window.
6. Answer the original question with the target, source, time, protocol, and
   supporting result. A CT record does not prove a live host, TCP success does
   not prove HTTP works, and HTTP 200 does not prove the user's workflow works.
   A remote node's top-level `null` means pending; after the deadline, report
   incomplete results rather than target failure.

Retry a temporary service error once, then use an alternative source and state
the limitation. Do not infer a blocking cause from one timeout. Continuous
monitoring, infrastructure changes, and trading requests are outside a one-off
check's scope.

## Sources

- [crt.sh](https://crt.sh/)
- [Check-Host API](https://check-host.net/about/api)
- [Hetzner Latency](https://hetzner-latency.sliplane.io/)
- [Ping-Admin](https://ping-admin.com/free_test/) · [API](https://ping-admin.com/texts/134.html)
- [CloudPingTest](https://cloudpingtest.com/)
- [Glassnode CEX methodology](https://latency.glassnode.com/cex/about)
