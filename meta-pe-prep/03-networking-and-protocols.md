# 03 · Networking and protocols (Meta Production Engineer)

> Compiled 2026-11-23.
> **Evidence tags.** `CR-25` / `CR-26` = first-hand candidate report from that year. `CR-old` = pre-2025. `AG` = prep or aggregator site. `PR` = practice item derived from a reported topic.
> **(snippet)** = the site blocks automated reads, so I saw only search excerpts; open the link to confirm.

---

## Where networking shows up

- **Generalist PE.** Networking is part of the online quiz (OA), "basic networking" inside the onsite Linux round, the new-grad "PE Basics" screen, and the design round.
  - Sources: [RW E4, 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`; [coditioning, Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.
  - One 2025 Glassdoor reviewer listed "TCP, UDP, https, DHCP, DNS, … load balance" ([Glassdoor PE](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).
  - Some guides still list a separate **Networking** round for PE ([Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`). Ask your recruiter.
- **Network Production Engineer (NPE).** NPE loops have a dedicated, deep networking round with heavy BGP content.
  - Sources: [Glassdoor NPE questions](https://www.glassdoor.co.in/Interview/Meta-Network-Production-Engineer-Interview-Questions-EI_IE40772.0,4_KO5,32.htm) (snippet; reports span roughly 2021–2026), e.g. [RVW97064399](https://www.glassdoor.com/Interview/Meta-Interview-E40772-RVW97064399.htm) and [RVW101709686](https://www.glassdoor.com/Interview/Meta-Interview-E40772-RVW101709686.htm); [LeetCode NPE intern](https://leetcode.com/discuss/interview-question/4625974/Meta-Network-Production-Engineer-Intern/) (snippet, `CR-old`).

**Depth guide.** Generalist PE candidates should be fluent in N1–N4, N7 and N9 and conversational in N5, N6 and N8. NPE candidates need all of it, plus OSPF/IS-IS, L2 and optics basics.

---

## N1. "What happens when you type www.facebook.com (or run `curl`)?"

- **Reported.** This is the most consistently reported networking prompt.
  - A 2025 Glassdoor report: "What happens when you type a URL in a browser?" (snippet).
  - [coditioning, 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`; [bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design) `AG`.
  - A 2025 Blind new-grad thread suggests tracing `curl www.facebook.com` end to end ([Blind](https://www.teamblind.com/post/interview-meta-production-engineer-university-grad-2025-6bneioqh), snippet).
- **Spine of the answer.**
  1. Parse the URL; check HSTS.
  2. **DNS.** Browser cache → OS stub resolver (`nsswitch`, `/etc/hosts`) → recursive resolver → root → `.com` → authoritative. The authoritative answer can depend on where the resolver is.
  3. **Transport.** A TCP three-way handshake, or QUIC.
  4. **TLS 1.3.** SNI, ALPN negotiates h2 or h3, certificate validation.
  5. **HTTP request.**
  6. **Edge.** Meta's public write-ups describe an L4 balancer ([Katran](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/), XDP/eBPF) in front of L7 proxies ([Proxygen](https://github.com/facebook/proxygen)).
  7. Origin, then the response, caching and rendering.
- **Follow-ups.**
  1. The page won't load. Which line of `curl -v` output tells you whether DNS, TCP, TLS or HTTP failed?
  2. What changes end to end with HTTP/3?
  3. How does a client pick IPv6 or IPv4 when it gets both? (Happy Eyeballs.)

## N2. TCP vs UDP; the handshake, teardown, flow control and congestion control

- **Reported.**
  - "Explain how TCP handshake works. What's the difference between TCP and UDP?" (2025 Glassdoor, snippet).
  - NPE: "TCP/IP, basic network topology, packet drop analysis, TCP flow control, and congestion control" ([Glassdoor NPE](https://www.glassdoor.co.in/Interview/Meta-Network-Production-Engineer-Interview-Questions-EI_IE40772.0,4_KO5,32.htm), snippet).
- **Core points.**
  - **Opening.** SYN → SYN-ACK → ACK, with random initial sequence numbers. Half-open connections wait in the *SYN queue*; completed ones wait in the *accept queue* until the app calls `accept()`. SYN cookies protect against SYN floods.
  - **Closing.** FIN and ACK in each direction. Whoever closes first holds `TIME_WAIT` for 2×MSL (60 s on Linux) so that late segments can't corrupt a new connection that reuses the same 4-tuple.
  - **Flow control** protects the *receiver*: rwnd, with window scaling.
  - **Congestion control** protects the *network*: cwnd, slow start, AIMD. CUBIC is Linux's default; BBR is model-based.
  - **Nagle + delayed ACK.** Together they can add about 40 ms to small writes; `TCP_NODELAY` turns Nagle off.
  - **UDP** has no connection, ordering or retransmission. It suits DNS, video and QUIC.
- **Follow-ups.**
  1. A host has 30,000 sockets in `TIME_WAIT`. Is that a problem? (On a *client* it can exhaust ephemeral ports; `tcp_tw_reuse` helps outbound connections; `tcp_tw_recycle` was removed in Linux 4.12.)
  2. The SYN-ACK is lost. What does each side do, and how long before `connect()` fails?
  3. Why does QUIC run over UDP instead of being a new IP protocol? (Middleboxes and kernel deployment speed.)

## N3. The TLS handshake

- **Reported.** "SSL/TLS handshakes" in the new-grad PE Basics screen ([coditioning, 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`). "https" in the 2025 Glassdoor topic list (snippet).
- **Core points.**
  - **TLS 1.2 vs 1.3.** TLS 1.2 takes 2 round trips. TLS 1.3 takes 1, using ECDHE key share in the ClientHello; resumption can be 0-RTT.
  - **0-RTT caveat.** 0-RTT data can be replayed, so allow it only for idempotent requests.
  - **Certificate validation.** The chain must reach a trusted root, the hostname must match a SAN, the dates must be valid, and revocation is checked (OCSP stapling).
  - **SNI** picks the certificate; **ALPN** picks h2 or h3.
  - Session tickets and PSKs allow resumption. Internal services often use **mTLS**.
- **Follow-ups.**
  1. Clients report certificate errors from 1 of 50 edge hosts. How do you find it, and how do you stop it happening again? (`openssl s_client -connect host:443 -servername …`; expiry monitoring; automated rotation.)
  2. Why terminate TLS at the edge rather than at the origin? What do you give up?
  3. Where does handshake latency come from on a 200 ms RTT mobile link, and what reduces it?

## N4. DNS resolution

- **Reported.**
  - A 2025 London report asked how DNS resolution works "behind the scenes" ([Glassdoor](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).
  - "How DNS works" in the NPE reports (snippet). DNS in the 2026 new-grad PE Basics screen ([coditioning](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide)).
- **Core points.**
  - **Roles.** Stub vs recursive vs authoritative resolvers; iterative resolution; glue records.
  - **Caching.** Answers are cached for their TTL. Failures (NXDOMAIN) are cached too, per the SOA.
  - **Record types:** A, AAAA, CNAME, NS, MX, TXT, SRV, PTR.
  - **Transport.** UDP 53. If a response is truncated (the TC bit), the client retries over TCP; zone transfers also use TCP. EDNS0 allows larger UDP responses.
  - **Debugging:** `dig +trace`, `dig @resolver name`, `resolvectl query`.
  - **Case study.** In Meta's [October 2021 outage](https://engineering.fb.com/2021/10/05/networking-traffic/outage-details/), a backbone change cut the data centers off. Meta's DNS servers are designed to withdraw their BGP announcements when they can't reach the data centers, and they all did, so `facebook.com` stopped resolving worldwide. Cloudflare's view from outside: [Cloudflare analysis](https://blog.cloudflare.com/october-2021-facebook-outage).
- **Follow-ups.**
  1. You changed an A record an hour ago, but some users still reach the old IP. Why? (TTLs, resolvers that ignore TTLs, client caches, connection reuse.)
  2. DNS lookups intermittently take exactly 5 s. (Resolver timeout and retry; parallel A/AAAA queries hitting a conntrack race; `options single-request` or `use-vc`.)
  3. You're designing health-based DNS failover. How do you choose the TTL, and what did the 2021 outage teach about health-based withdrawal?

## N5. BGP and anycast

- **Reported (mainly NPE).** All from [Glassdoor NPE](https://www.glassdoor.co.in/Interview/Meta-Network-Production-Engineer-Interview-Questions-EI_IE40772.0,4_KO5,32.htm) (snippet):
  - BGP vs OSPF; eBGP vs iBGP; loop prevention; "How does BGP choose the best path?"; "the categories of BGP attributes."
  - "Why do we need the open messages, why can't we use only the TCP 3-way handshake?" and the reasons a peering session fails.
  - **Anycast does not appear in any report I found.** It's `PR`, but it's the natural follow-up given Meta's edge design and the 2021 outage.
- **Core points.**
  - **What each protocol is.** BGP is a path-vector EGP that runs over TCP 179. OSPF is a link-state IGP.
  - **Loop prevention.** eBGP uses AS_PATH. iBGP doesn't re-advertise routes learned from one iBGP peer to another, so you need a full mesh or route reflectors.
  - **Best-path order (simplified):** highest LOCAL_PREF → locally originated → shortest AS_PATH → lowest origin → lowest MED → eBGP over iBGP → lowest IGP cost to the next hop → tiebreakers (router ID). Cisco's WEIGHT comes before all of these.
  - **Attribute categories.** Well-known mandatory (AS_PATH, NEXT_HOP, ORIGIN); well-known discretionary (LOCAL_PREF); optional transitive (COMMUNITY); optional non-transitive (MED).
  - **What OPEN is for.** TCP only provides transport. OPEN negotiates the BGP version, AS number, hold time, router ID, and capabilities such as multiprotocol, 4-byte ASNs and graceful restart.
  - **Why sessions fail:** TCP 179 blocked; wrong neighbor IP or AS; the TTL is 1 for eBGP but the peer is multihop; MD5 password mismatch; hold-timer expiry; max-prefix exceeded; capability mismatch; wrong update-source.
  - **Anycast.** Many sites announce the same prefix, and BGP sends each client to the "closest" site by policy and AS path (not by geography). It suits UDP and DNS. TCP works as long as routes stay stable.
- **Follow-ups.**
  1. How do you drain an anycast site without blackholing traffic? (Withdraw or AS-prepend gradually; watch how traffic shifts to the other sites.)
  2. A route flap moves a client to a different anycast site mid-connection. What happens to its TCP session? And to a QUIC connection?
  3. Your peering session flaps every 90 seconds. What's your first hypothesis? (Hold-timer expiry: keepalives are being dropped, or the CPU or control plane is overloaded.)

## N6. HTTP/1.1, HTTP/2 and HTTP/3 (QUIC) (`PR`; not in the PE reports I found, but central to Meta's edge)

- **Core points.**
  - **HTTP/1.1** handles one request at a time per connection (keep-alive), so clients open many connections.
  - **HTTP/2** has binary framing and multiplexes streams over **one TCP connection**, with HPACK header compression. Its weakness is that one lost packet stalls every stream: TCP head-of-line blocking.
  - **HTTP/3** runs over **QUIC on UDP**:
    - Streams are independent at the transport layer.
    - TLS 1.3 is built into the handshake (1-RTT, or 0-RTT on resumption).
    - Connection IDs let a connection survive the client changing IP address.
    - It uses QPACK for header compression.
    - It's implemented in user space. Meta's implementation is [mvfst](https://github.com/facebook/mvfst).
    - Clients discover it via `Alt-Svc` or the DNS HTTPS record, and fall back to TCP when UDP 443 is blocked.
- **Follow-ups.**
  1. Why can HTTP/2 perform *worse* than HTTP/1.1 on a lossy mobile network?
  2. A client's IP changes mid-session. How does an L4 load balancer keep routing its QUIC packets to the same backend? (Route on the connection ID, not the 5-tuple.)
  3. What new operational headaches does QUIC bring? (UDP CPU cost, so GSO/GRO matter; middleboxes; encrypted headers make packet-level debugging harder.)

## N7. Load balancing: L4 vs L7

- **Reported.** "load balance" in a 2025 Glassdoor topic list (snippet). Load balancers also come up in nearly every design round (file 04).
- **Core points.**
  - **L4** routes on the 5-tuple and never looks at the payload. It is cheap and can do direct server return.
    - **Consistent hashing** (such as Maglev) lets a fleet of balancers agree on the same backend with no shared state.
    - Katran's write-up describes ECMP from routers to the LB hosts, IPIP encapsulation to the backends, and XDP/eBPF forwarding.
  - **L7** terminates TCP and TLS and routes on host, path or headers. It also handles retries, rate limits, auth, connection pooling and rich metrics. The price is CPU and added latency.
  - **Health checks** can be active probes or passive (outlier ejection). Also know connection draining and slow-start.
  - **Algorithms:** round robin, least connections, power-of-two-choices, consistent hashing.
- **Follow-ups.**
  1. You add a backend. How many existing connections move under modulo hashing, and how many under consistent hashing?
  2. One backend receives 3× its share of traffic. List the possible causes. (Long-lived connections; a hot hashing key; a broken health check that's pulling its peers out; slow-start disabled.)
  3. How do you take a host out of service without dropping in-flight requests?

## N8. Linux network stack tuning (`PR` beyond the reported mentions of `tcpdump` and netcat)

- **The receive path.** NIC → RX ring (`ethtool -g`) → IRQ → NAPI softirq (`netdev_budget`) → RPS/RFS → IP → TCP → socket receive buffer → application.
- **Knobs worth knowing.**
  - `net.core.somaxconn`, raised together with the app's `listen()` backlog; `net.ipv4.tcp_max_syn_backlog`; `tcp_syncookies`.
  - `net.ipv4.ip_local_port_range`; `tcp_tw_reuse`.
  - `net.core.rmem_max`/`wmem_max` and `tcp_rmem`/`tcp_wmem` (receive-buffer autotuning).
  - `net.core.netdev_max_backlog`; `net.ipv4.tcp_congestion_control=bbr` with the `fq` qdisc.
  - `nf_conntrack_max`. When it's too small you see `nf_conntrack: table full, dropping packet`.
  - `ulimit -n`; IRQ affinity and `irqbalance`; the GRO/GSO/TSO offloads.
- **Diagnostics:** `ss -tin`, `nstat -az`, `netstat -s`, `ethtool -S` (NIC drops), `/proc/net/softnet_stat` (`dropped`, `time_squeeze`), `ip -s link`.
- **Follow-ups.**
  1. Packets are being dropped. How do you tell whether it's at the NIC, in the kernel backlog, or at the socket?
  2. Under load, outbound connections fail with `EADDRNOTAVAIL` ("cannot assign requested address"). What's the cause, and what are three fixes?
  3. Why must `somaxconn` and the application's backlog be raised together?

## N9. Network troubleshooting scenarios (reported)

- **Sources.** "Troubleshoot a server that's not reachable"; "debug a slow download from the other side of the world"; "packet drop analysis" ([Glassdoor NPE](https://www.glassdoor.co.in/Interview/Meta-Network-Production-Engineer-Interview-Questions-EI_IE40772.0,4_KO5,32.htm), snippet).
- **The server isn't reachable.** Work up the layers:
  - Link: `ip link`.
  - Address and route: `ip addr`, `ip route get <dst>`.
  - Neighbors: `ip neigh`.
  - Firewall: `nft list ruleset` or `iptables -S`.
  - Is the service listening? `ss -ltnp`.
  - Name resolution: DNS.
  - Path: `ping`, `mtr`, `traceroute -T -p 443`.
  - Packets: `tcpdump` on **both** ends.
- **The slow long-haul download.**
  - Compute the bandwidth-delay product: 1 Gb/s × 200 ms ≈ 25 MB must be in flight to fill the pipe.
  - Check window scaling and the `rmem` maximums, the retransmit rate (`ss -ti`), and per-hop loss (`mtr`).
  - Try BBR; measure with `iperf3`.
- **Follow-ups.**
  1. `ping` works but HTTP doesn't.
  2. Small requests work but large ones hang. (An MTU or PMTUD black hole.)
  3. Loss shows up only in one direction. How do you prove it?

## N10. Addressing basics (OA level)

- **Reported.** The OA covers "networking" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`). Prepfully's prep advice includes IP addressing and subnetting. IPv4 vs IPv6, ping and latency appear in the 2026 new-grad PE Basics screen ([coditioning](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide)). DHCP appears in a 2025 Glassdoor list (snippet).
- **Core points.**
  - CIDR math: a /24 has 256 addresses and 254 usable hosts; a /27 has 32 addresses and 30 hosts.
  - RFC 1918 private ranges; NAT; ARP.
  - DHCP's DORA exchange.
  - IPv6 basics: SLAAC vs DHCPv6, link-local addresses, no broadcast. Meta has publicly discussed running its data centers largely IPv6-only.
- **Follow-ups.**
  1. Two hosts on one LAN end up with the same IP. What do users see, and how do you find the culprit?
  2. How many /26 subnets fit in a /22?
  3. What replaces ARP in IPv6? (Neighbor Discovery, using ICMPv6.)

---

## Worked example: a 3-minute model answer to "What happens when you type www.facebook.com?" (`PR`)

Give the whole path first, briefly. Then let the interviewer choose where to go deep. The **[hooks]** mark the places they usually stop you.

1. **The browser.** It parses the URL, sees HTTPS (and an HSTS entry), and checks its caches: DNS cache, connection pool, and the HTTP cache for an existing response. **[hook: HSTS preload, an existing connection being reused]**
2. **DNS.** On a cache miss, the OS stub resolver checks `/etc/hosts` according to `nsswitch.conf`, then sends a UDP query to the configured recursive resolver.
   - The recursive resolver walks root → `.com` → the authoritative servers for `facebook.com`, caching each answer for its TTL.
   - The authoritative answer is usually a **CNAME to an edge hostname**, then an A/AAAA record chosen for where the resolver is.
   - **[hooks: TTL trade-offs, EDNS Client Subnet, negative caching, the October 2021 outage]**
3. **Transport.** The client gets both an AAAA and an A record, and Happy Eyeballs races IPv6 against IPv4.
   - The TCP three-way handshake goes to the edge POP's virtual IP. If the client already knows the site speaks HTTP/3, it uses **QUIC over UDP 443** instead.
   - **[hooks: SYN/accept queues, SYN cookies, why QUIC uses UDP]**
4. **TLS 1.3.**
   - The ClientHello carries the SNI `www.facebook.com`, a key share, and ALPN offering `h2` or `h3`.
   - The server returns its certificate chain. The client checks the chain, the SAN and the expiry.
   - That's one round trip, or zero with session resumption. **[hooks: 0-RTT replay risk, OCSP stapling, mTLS internally]**
5. **At Meta's edge** (from public write-ups):
   - Routers spread packets across L4 load balancers using ECMP.
   - The L4 layer (**Katran**, XDP/eBPF) consistent-hashes each flow to an L7 proxy host (**Proxygen**), which terminates TLS and HTTP.
   - **[hooks: L4 vs L7, consistent hashing, health checks, draining]**
6. **Edge to origin.** The proxy serves cacheable content from the POP, or forwards the request over Meta's backbone to a data-center L7 tier, then to the web/app servers and their caches and databases. **[hooks: connection pooling, retries, timeouts, backpressure]**
7. **The response.** The HTTP response streams back over the same multiplexed connection. The browser parses the HTML, fetches subresources over that connection (often from CDN hostnames), and renders the page. **[hooks: HTTP/2 vs HTTP/3 head-of-line blocking, caching headers]**

**Close by inviting the depth choice:** "I can go deeper on any layer. DNS and the edge load balancing are probably the most interesting parts at Meta's scale."

**Debugging version of the same answer.** If asked "the page won't load, where do you look?", walk the same layers using `curl -v`:
- `* Could not resolve host` → **DNS**: use `dig`.
- `* connect to … failed` or a timeout → **TCP**: routing, firewall, or the listener. Use `mtr`, `ss`, `tcpdump`.
- `SSL certificate problem` → **TLS**: use `openssl s_client`.
- An HTTP 4xx/5xx → **the application or the proxy**: check the logs.

---

## Checking these threads yourself

- **Reddit** (I couldn't reach it). Search these in your browser:
  - `site:reddit.com meta "network production engineer" interview`
  - `site:reddit.com/r/networking meta NPE interview BGP`
- **Meta primary sources** worth skimming before an interview: [October 2021 outage details](https://engineering.fb.com/2021/10/05/networking-traffic/outage-details/), [Katran](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/) ([GitHub](https://github.com/facebookincubator/katran)), [mvfst (QUIC)](https://github.com/facebook/mvfst), [Proxygen](https://github.com/facebook/proxygen).
