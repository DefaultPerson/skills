# CT and distributed checks

## crt.sh

Send GET requests to `https://crt.sh/` with URL-encoded parameters `q=<domain>`
and `output=json`. For subdomains, query `%.<domain>` (encode the percent sign
as `%25`). Query the exact domain separately if needed. Do not add undocumented
pagination or limit parameters. Set a request timeout, such as 25 seconds.

Expect a JSON array; an HTML error, a timeout, and an empty array are distinct
outcomes. Preserve ID, common_name/name_value, issuer_name, not_before/not_after,
and entry_timestamp when present. Split name_value on newlines, deduplicate,
and retain only the requested domain and its subdomains using a dot boundary.
Keep `*.example.com` as a wildcard pattern, not a discovered live host.
Preserve originals during normalization. DNS/HTTPS validation is a separate step.

A certificate's validity in CT does not prove that the server currently presents
that certificate. Historical names and certificates can remain after a host is
removed. Repeated 502s or timeouts mean the query is unavailable from this
environment, not that no certificates exist. Use another CT index if necessary
and identify the source.

## Check-Host

Send all GET requests with `Accept: application/json`:

- `/nodes/hosts` — current node hostnames, locations, ASNs, and IPs.
- `/check-<type>?host=<encoded-target>&max_nodes=N` — start a check; type: ping/http/tcp/dns/udp.
- Repeat the `node=<hostname>` parameter to select specific nodes.
- `/check-result/<request_id>` — per-node results.
- `/check-result-extended/<request_id>` — metadata and results when the creation time and command are needed.

The start response contains `ok`, `request_id`, `permanent_link`, and `nodes`.
`ok: 1` means only that the request was accepted. Wait for each selected node
or the deadline. A top-level `null` means that node is still working; interpret
nested nulls and error arrays according to the check type, not as endless waiting.

API timings are in seconds; multiply by 1000 for milliseconds and label the
units. An HTTP result array contains success, duration, message, status code,
and IP when available. TCP returns time/address or error; ping returns individual
attempts; DNS returns records and TTL. Preserve the original structure rather
than assuming one common result format across protocols.

The bundled client requires Python 3 and curl, without API keys. By default,
it selects 3 nodes and waits up to 45 seconds, including check creation. It
outputs JSON containing raw results, metadata, and pending nodes. Exit 0 means
collection is complete, **not** that the target is healthy; exit 2 means partial
collection or an API error. `--deadline` sets the total limit from 5 to 60 seconds.
If polling fails, previously collected results and the request ID are retained.

## Sources

- [crt.sh JSON implementation](https://github.com/crtsh/certwatch_db/blob/master/fnc/web_apis.fnc)
- [Check-Host API and result formats](https://check-host.net/about/api)
