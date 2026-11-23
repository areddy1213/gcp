# 04 · System design and architecture (Meta Production Engineer)

> Compiled 2026-11-23.
> **Evidence tags.** `CR-25` / `CR-26` = first-hand candidate report from that year. `CR-old` = pre-2025. `AG` = prep or aggregator site. `PR` = practice item or my own synthesis.
> **(snippet)** = the site blocks automated reads, so I saw only search excerpts; open the link to confirm.

---

## What's reported about the round

- **Experienced loops include one PE-flavored design round.**
  - A 2025 E4 candidate got a "standard Production Engineer system design question" and rated it their weakest round: "I don't think I demonstrated enough depth." In hindsight they "should have spent more time on PE-specific design considerations."
    - Sources: [RW E4, Mar 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`.
  - A late-2024 candidate described "designing a practical system to solve a real-world problem," "more grounded in practicality." Their advice: be ready with "detailed and practical solutions, not just theoretical designs."
    - Sources: [Bala Krishnan, Dec 2024](https://bala-krishnan.com/posts/18-meta/) `CR-old`.
- **New-grad loops have no dedicated design round**, although design fundamentals still come up in other rounds.
  - Sources: [coditioning, Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.
- **Candidates struggle to find PE-specific prep.** A Dec 2025 Blind thread notes that the resources out there are SWE system design.
  - Sources: [Blind: Meta production eng system design prep](https://teamblind.com/post/meta-production-eng-system-design-prep-vc7rqzkg) (snippet).
- **Prepfully's framing.** The prompt is ambiguous. Ask clarifying questions, "develop a simple and practical solution," and weigh load, monitoring, and "what not to consider."
  - Sources: [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`.
- **An older pub/sub report.** The interviewer pushed a broad pub/sub prompt down into "storage & bandwidth calculation; distributed consensus and network partition tolerance; ddos and bot."
  - Sources: [Glassdoor review](https://www.glassdoor.co.uk/Interview/Meta-Interview-E40772-RVW12130829.htm) (snippet, `CR-old`; the date is unclear, but the depth expectation matches the 2025 reports).
- **2026 context (SWE pipeline).** SWE onsites now include an "AI-Enabled System Design" round. Whether PE loops changed is **not reported**; ask your recruiter.
  - Sources: [1point3acres 2026 Q4 trends](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4) `AG`.

---

## How PE design is judged differently from SWE design

Meta publishes no PE design rubric. The table is **my synthesis** (`PR`) of the evidence below it.

| Dimension | Typical SWE product-design emphasis | PE design emphasis |
|---|---|---|
| Starting point | Features, API, data model | SLOs, load profile, failure domains, and what *not* to build |
| Depth | Breadth across components | One level lower: what runs on each host, kernel and network limits, how the process is deployed and restarted |
| Capacity math | QPS and storage | Also bandwidth, fan-out, per-host limits (fds, connections, NIC), headroom to survive losing a region (N+1 / N+2) |
| Failure | "Add replicas" | Walk each component's failure modes: how it's detected, blast radius, mitigation, recovery time; correlated failures; network partitions |
| Change safety | Rarely discussed | Central: staged code *and* config rollouts, canaries, automatic rollback, kill switches |
| Observability | "Add monitoring" | Which SLIs, what alerts and at what thresholds, how you'd debug it at 3 a.m., who monitors the monitoring |
| Overload | Autoscaling | Backpressure, load shedding, rate limits, retry budgets, circuit breakers, graceful degradation |
| Operations | Out of scope | On-call, runbooks, DR drills, capacity-planning cadence, automating toil away |

**The evidence behind the table**
- **Simplicity and practicality:** "Simple and practical," load, monitoring, "what not to consider" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer)); "practical solutions, not just theoretical designs" ([Bala](https://bala-krishnan.com/posts/18-meta/)).
- **Behavior under load:** Prepfully's systems round assesses "understanding of systems at scale and their behaviour under load" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer)).
- **Partial failure:** Show how the design behaves under partial failure, and raise single points of failure early ([Prepfully design guidance](https://prepfully.com/accelerate/meta-production-eng), snippet).
- **Depth on demand:** Storage and bandwidth math, consensus, partition tolerance, DDoS ([Glassdoor](https://www.glassdoor.co.uk/Interview/Meta-Interview-E40772-RVW12130829.htm), snippet).
- **Operations topics:** HA and failover; metrics, logs, tracing and alerting (SLOs, SLIs, error budgets); incident response; capacity planning; backpressure; graceful degradation ([bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design) `AG`, one candidate's advice).
- **The whole lifecycle:** "The entire lifecycle of a service, from development to production" ([RW: PE system design questions, Aug 2025](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design)).
- **Infrastructure flavor:** The round is "more infrastructure-oriented than a standard product round" ([cleverprep](https://www.cleverprep.com/companies/meta/production-engineer) `AG`).
- **Seniority:** At E5 and above (SWE data), you're expected to "drive the whole conversation" on scope, approach, scale *and failure* ([intervue.io, Nov 2026](https://www.intervue.io/blog/meta-interview-experience)).

---

## A 45-minute PE answer skeleton (`PR`)

| Time | Do this | Say something like |
|---|---|---|
| 0–5 | Clarify: users, QPS, data size, latency and availability SLOs, consistency, durability, what's out of scope | "I'll target 99.9% availability for writes. Is losing the last few seconds of data acceptable?" |
| 5–10 | Capacity estimate (cheat sheet below) | "About 1 GB/s ingest, so roughly 86 TB/day raw and about 260 TB/day at 3× replication." |
| 10–20 | The simplest design that works; draw the data flow | "Version one is a single region. I'll add the second region once the failure walk shows we need it." |
| 20–35 | **Failure-mode walk**, component by component: detection → blast radius → mitigation → recovery | "If the broker leader dies, the ISR elects a new one in about 10 s, so producers buffer and retry. Here's the alert." |
| 35–40 | Rollout and config safety; observability (SLIs, alerts, dashboards, tracing) | "Config goes through the same canary process as code. A host keeps its last-known-good config if it can't fetch a new one." |
| 40–45 | Overload and degradation; trade-offs; what you'd do next | "Under overload we drop debug-level logs first and never drop the audit stream." |

**Capacity cheat sheet** (orders of magnitude)
- **Request rates.** One day ≈ 86,400 s ≈ 10⁵ s, so 1M requests/day ≈ 12 QPS and 1B requests/day ≈ 12k QPS.
- **Network.** A 10 GbE NIC moves about 1.25 GB/s. RTT is about 0.5 ms within a data center, about 80–100 ms US↔EU, and about 150–200 ms US↔Asia.
- **Memory and storage.** A RAM access takes about 100 ns; an NVMe random read takes about 100 µs; an HDD does about 100–200 IOPS at about 150–200 MB/s sequential.
- **Fan-out.** Pushing a 100 MB file to 1M hosts from one source is 100 TB of egress. That's why fleets use tree or peer-to-peer distribution (see D4).

---

## Prompt families

### D1. Distributed message broker, pub/sub, messaging platform
- **Reported.**
  - "Design a system for managing a distributed message broker" (recently reported) and "How would you design a scalable messaging platform?" ([Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`).
  - Pub/sub with storage and bandwidth math, consensus and partitions ([Glassdoor](https://www.glassdoor.co.uk/Interview/Meta-Interview-E40772-RVW12130829.htm), snippet).
  - A real-time chat app ([Prepfully PE question bank](https://prepfully.com/interview-questions/meta/production-engineer), snippet).
- **PE talking points.**
  - **The core structure.** A partitioned, append-only log. Each partition has a replication factor and an acknowledgment quorum (ISR or Raft). Leader election goes through a consensus service.
  - **Consumers.** Consumer groups track their offsets. Deliver at least once, and make consumers idempotent.
  - **Storage over time.** Retention limits, with tiered storage for older data.
  - **Operational hazards.** Hot partitions; rebalancing storms; a broker's disk filling up (this links back to the Linux round); cross-region replication lag.
  - **Capacity.** messages/s × message size × replication factor × retention.
- **Follow-ups.**
  1. One broker's disk fills. What do producers see, and how does the system degrade?
  2. A consumer group falls 6 hours behind. What are your options? (Add consumers up to the partition count; skip ahead; replay later.)
  3. A network partition splits the brokers. How do you avoid split brain, and what does a producer using `acks=all` experience?

### D2. Real-time telemetry, logging and metrics ingestion
- **Reported.**
  - "Design a system for real-time processing of medical sensor data" (recently reported, [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`).
  - "Design a Log Aggregation and Analysis System"; "Design a System to Monitor the Health and Performance of a Large Microservices Architecture"; "Design a Distributed Tracing System." The author tagged each with Meta among other companies ([RW, Aug 2025](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design)).
  - Aggregator variants (unverified): "monitoring and alerting for Meta's infrastructure"; "log aggregation for millions of servers" ([cleverprep](https://www.cleverprep.com/companies/meta/production-engineer), [extrabrain](https://extrabrain.app/interview-questions/meta-production-engineer-interview-extrabrain/)).
- **PE talking points.**
  - **On the host.** An agent with a local disk buffer. Scribe, Meta's log transport, uses a per-host daemon that buffers to memory and disk when downstream is unavailable ([Scribe](https://engineering.fb.com/2019/10/07/data-infrastructure/scribe/)).
  - **In transit.** Batching and compression; schemas; sampling.
  - **Separate pipelines.** Metrics, logs and traces each get their own path.
  - **Storage tiers.** Hot data in an in-memory time-series DB ([Gorilla, VLDB 2015](https://www.vldb.org/pvldb/vol8/p1816-teller.pdf)); warm storage; a cold archive.
  - **Risks.** Label-cardinality explosions; late or out-of-order data.
  - **Alerting independence.** The alerting path must not depend on the pipeline it monitors.
  - **Shedding order under overload.** Drop debug logs first; never drop audit records.
  - **For the medical variant.** Durability and latency SLOs, privacy, and devices with intermittent connectivity.
- **Follow-ups.**
  1. Ingestion is down for 30 minutes. What happens on a million hosts? (Disk buffers fill. What's the drop policy, and what happens on recovery: does the backlog stampede the pipeline?)
  2. A team adds a `user_id` label, and the series count grows 1000×. How do you detect it, and how do you protect everyone else?
  3. How are you alerted when the monitoring system itself is down? (A dead-man's switch; probes from outside.)

### D3. Deployment and orchestration
- **Reported.**
  - "Design a Global Software Deployment System (aka CD)" (author's tags: Google, Meta). "Design an Automated Release Management System (CI + CD)" (Meta, Apple). "Design a Large-Scale Linux Kernel Update System" (Apple, Meta). All from [RW, Aug 2025](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design).
  - "Design a deployment system that prevents a bad release from reaching all users" ([cleverprep](https://www.cleverprep.com/companies/meta/production-engineer) `AG`).
  - The screen-level "failing deployments" troubleshooting prompt (file 02, B3) makes this the most PE-native design family.
- **PE talking points.**
  - **Artifacts.** Build once, sign it, and deploy the same artifact everywhere.
  - **Staged rollout with automated gates.** Canary → 1% → one region → global. At each stage, compare the canary's error rate, latency and crash loops against a control group.
  - **Automatic rollback** when a gate fails.
  - **Desired-state model.** A desired-state controller drives idempotent agents on the hosts.
  - **Limits on change.** Cap the hosts in flight per failure domain; deploy in dependency order; honor freeze windows.
  - **Kernel updates specifically.** Drain hosts before rebooting; choose between `kexec`, a full reboot, or live patching; keep enough capacity while hosts are drained; use out-of-band (BMC) access to recover hosts that won't boot.
- **Follow-ups.**
  1. The canary looked healthy, but the bug appears only at 100% traffic. How could you have caught it?
  2. The rollback itself fails because the release ran an incompatible schema migration. What now, and how do you prevent it next time? (Expand/contract migrations.)
  3. How do you deploy the deployment system?

### D4. Fleet-wide configuration management, file distribution, feature flags
- **Reported.**
  - "Design a Large-Scale File Distribution System" (Meta, Google) and "Design a Distributed Configuration Management System" (Google, Microsoft; *not* Meta-tagged) ([RW, Aug 2025](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design)).
  - "A configuration distribution system with safe rollout and rollback" ([cleverprep](https://www.cleverprep.com/companies/meta/production-engineer) `AG`).
  - "Distributed feature flag system" ([Prepfully question bank](https://prepfully.com/interview-questions/meta/production-engineer), snippet).
- **PE talking points.**
  - **Config is code.** It gets review, validation, canarying and staged distribution: Meta's Configerator model ([Holistic Configuration Management at Facebook, SOSP 2015](https://web.eecs.utk.edu/~qcao1/cs560/papers/holistic.pdf); [summary](https://blog.acolyer.org/2015/10/16/holistic-configuration-management-at-facebook/)).
  - **Large payloads need peer-to-peer or tree distribution.** Meta's Location-Aware Distribution replaced a ZooKeeper-based path and raised the practical update size from about 5 MB to about 100 MB ([LAD](https://engineering.fb.com/2018/07/19/data-infrastructure/location-aware-distribution-configuring-servers-at-scale/)).
  - **Delivery model.** Push vs pull; versioned, atomic swaps.
  - **Survive a config-service outage.** Every host keeps a **last-known-good** cache, so the fleet keeps running.
  - **Big red buttons.** Kill switches.
  - **Feature flags.** Evaluate locally against cached rules; bucket users with a stable hash for percentage rollouts; clean up stale flags.
  - **File distribution.** Content-addressed chunks with checksums; rack-aware peers; bandwidth caps so distribution doesn't hurt production traffic.
- **Follow-ups.**
  1. A bad config reaches the whole fleet in 30 seconds and crashes the service. Which design choices limit the blast radius? (Staged config rollout; validators; and, as the 2021 outage showed, the safety tooling itself needs testing.)
  2. Hosts can't reach the config service at boot. What should they do?
  3. Distribute a 5 GB model file to a million hosts within 10 minutes. Estimate the bandwidth, then design it.

### D5. CDN, caching, KV store, storage
- **Reported.**
  - CDN, distributed key-value store, Netflix-style video streaming ([Prepfully question bank](https://prepfully.com/interview-questions/meta/production-engineer), snippet).
  - "Design a CDN… built from Nginx and OS-level building blocks" (author's tag: Warner Brothers). "Design a Distributed Storage System (like HDFS or S3)" (Google, Meta). Both from [RW](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design).
- **PE talking points.**
  - **CDN.**
    - Choose a POP via DNS or anycast (file 03).
    - Cache hierarchy: edge → regional → origin shield. Define the cache key; TTLs plus purge.
    - Protect the origin: request coalescing on a miss; stale-while-revalidate or serve-stale when the origin fails, which is your graceful degradation.
    - Per-POP capacity: disk and NIC. DDoS absorption.
  - **KV store.** Consistent hashing; N replicas with quorum reads and writes (R + W > N); hinted handoff and anti-entropy repair; hot keys; leases to prevent a thundering herd when a hot key expires.
  - **Storage.** Chunking; replication vs erasure coding; a metadata service; rebalancing; placement across failure domains; durability targets ("nines").
- **Follow-ups.**
  1. The origin goes down. What do users see, and for how long?
  2. A celebrity post makes one key 1000× hotter. What breaks, and how do you fix it?
  3. Purges take 10 minutes to propagate, but legal needs content gone within one minute. What do you change?

### D6. Reliability building blocks and critical services
- **Reported.**
  - "Design a Rate Limiter for a Public API" (Google, Meta). "Design a Circuit Breaker System" (Netflix/Google, Meta). "Design a High-Availability System for a Critical Service (e.g., a payment gateway or DNS service)" targeting 99.999%. "How would you handle a major outage for a critical service?" All from [RW](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design).
- **PE talking points.**
  - **Rate limiting.** Token bucket vs sliding window. Local vs global counters: a central store is accurate but becomes a dependency; per-host quotas are approximate but resilient. Decide fail-open vs fail-closed. Return `429` with `Retry-After`.
  - **Circuit breakers.** Closed → open → half-open states. Pair them with retry budgets and deadline propagation, which prevent retry storms and cascading failure.
  - **What 99.999% means.** It allows about 5.3 minutes of downtime a year. You need active-active multi-region, no single control-plane dependency, automated failover, and regular DR tests.
- **Follow-ups.**
  1. The rate limiter's datastore goes down. Should the limiter fail open or closed, and does the answer depend on the endpoint?
  2. Client retries amplified an outage 10×. What would you change on the clients and on the servers?
  3. How do you show a service will meet 99.99% *before* you launch it?

### D7. Other prompts reported for PE
- **The prompts.** "Design a buy-now-pay-later system for Meta"; "an e-commerce checkout system" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`). "Design a Botnet for Web Scraping," explicitly *with ethical considerations as a key discussion point* ([RW](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design), Meta-tagged).
- **The PE twist** on these product-style prompts:
  - Make payment operations safe to repeat, using idempotency keys.
  - Plan for external payment providers that are slow or down: queue, retry with backoff, show the user a pending state.
  - Reconcile with the providers.
  - For a fleet of scrapers: scheduling, politeness and rate limiting, and IP reputation. Be clear about the ethical and legal limits.
- **Follow-ups.**
  1. The payment provider times out. Did the charge happen? How do you find out without charging twice?
  2. Which parts of checkout can degrade, and which must fail closed?
  3. How do you keep a scraping fleet from becoming a DoS against the sites it crawls?

---

## Meta primary sources worth skimming

| Topic | Read |
|---|---|
| Logging transport | [Scribe: transporting petabytes per hour](https://engineering.fb.com/2019/10/07/data-infrastructure/scribe/) |
| Config management | [Holistic Configuration Management at Facebook (SOSP 2015)](https://web.eecs.utk.edu/~qcao1/cs560/papers/holistic.pdf) · [Location-Aware Distribution](https://engineering.fb.com/2018/07/19/data-infrastructure/location-aware-distribution-configuring-servers-at-scale/) |
| L4 load balancing | [Katran](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/) |
| Time-series metrics | [Gorilla (VLDB 2015)](https://www.vldb.org/pvldb/vol8/p1816-teller.pdf) |
| Failure case study | [October 2021 outage details](https://engineering.fb.com/2021/10/05/networking-traffic/outage-details/) |

One Glassdoor reviewer advises studying popular Meta research papers and conference talks for this round ([Glassdoor PE](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).

**Design prep candidates cited:** [The System Design Primer](https://github.com/donnemartin/system-design-primer) and [Hello Interview](https://www.hellointerview.com/learn/system-design/in-a-hurry/introduction) problems ([RW E4](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview), [Bala](https://bala-krishnan.com/posts/18-meta/)). Treat these as SWE baselines, then add the PE dimensions from the table above.

## Checking these threads yourself

- **Reddit** (I couldn't reach it). Search these in your browser:
  - `site:reddit.com meta "production engineer" "system design"`
  - `site:reddit.com/r/sre "production engineer" design round meta`
- **Blind:** [PE system design prep (Dec 2025)](https://teamblind.com/post/meta-production-eng-system-design-prep-vc7rqzkg).
