# 02 · Linux systems and troubleshooting (Meta Production Engineer)

> Compiled 2026-11-23.
> **Evidence tags.** `CR-25` / `CR-26` = first-hand candidate report from that year. `CR-old` = pre-2025 report. `AG` = prep or aggregator site. `PR` = practice item derived from a reported topic.
> **(snippet)** = the site blocks automated reads, so I saw only search-engine excerpts; open the link to confirm.

---

## What the round looks like (as reported)

- **Screen: a troubleshooting exercise with moving goalposts.** The 2025 prompt was "Uncle Bernie's Website is down. Figure out why." The interviewer "kept moving the goalposts." The root cause was a disk out of space.
  - Sources: [RW E4, Mar 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`.
- **Screen: failing deployments.** The Linux half of one screen was "Troubleshooting failing deployments."
  - Sources: [RW Prep to Offer](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) `CR-25` (screened Oct 2024).
  - A 2025 phone screen was summarized as "diagnosing deployment failures and CI/CD pipeline troubleshooting": [1point3acres 1130439, Apr–Jun 2025](https://www.1point3acres.com/interview/thread/1130439) (login required).
- **Onsite Linux round: practical, not trivia.** It consisted of "Interactive troubleshooting sessions with 15-minute timeboxes." It was all Linux, with "no Docker, Kubernetes, or specific DB implementation trivia." It tested "real troubleshooting skills rather than memorized knowledge."
  - Sources: [RW Prep to Offer](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) `CR-25`.
- **Onsite Linux topics.** Memory management, processes, file systems, security fundamentals, basic networking.
  - Sources: [RW E4](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`.
- **"Systems Internals" round (late 2024).** Three parts: troubleshoot a server, "explain the output of specific Linux commands", and internals (processes, memory allocation, I/O).
  - Sources: [Bala Krishnan, Dec 2024](https://bala-krishnan.com/posts/18-meta/) `CR-old`.
- **Interviewers vary in emphasis.** "Some focus on Linux internals while some focus on scenario based" questions. Another warning: interviewers "dig deep into whatever u say."
  - Sources: [Glassdoor PE](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm) (snippet).
- **Prepfully's description.** About 45 minutes, starting from an unhealthy web server or database. It covers system calls, `tcpdump`, memory allocation, swapping, and the UNIX process lifecycle.
  - Sources: [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`.
- **New-grad troubleshooting prompts (2026).** "Troubleshoot a slow web server." "A server keeps crashing every five minutes, then restarts automatically." "A web server is slow despite normal resource metrics."
  - Sources: [coditioning, Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.

**How to run the round.**
- Narrate each step as *hypothesis → command → what I expect → what it rules out*.
- Mitigate first, then find the root cause, then prevent a repeat. Capture state before you restart anything.
- Expect the interviewer to change the facts partway through. That is part of the test, not a sign that you are wrong.

---

## A. Linux internals deep dives

Each card lists what has been reported, the core points to say, and the follow-ups.

### A1. Processes vs threads; `fork` and `exec`
- **Reported.** "What is the difference between a process and a thread?" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer), [coditioning](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`). Threads appear in "threads, virtual memory, mmu, signals, file systems" ([Glassdoor](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).
- **Core points.**
  - Both are created with `clone()`. Threads share the address space, the fd table and the signal handlers. Each thread has its own stack, registers and TID; `getpid()` returns the thread-group ID.
  - `fork()` copies page tables and uses copy-on-write (COW), so pages are only copied when written. `exec()` replaces the program image but keeps the open fds unless `O_CLOEXEC` is set.
- **Follow-ups.**
  1. After `fork()`, parent and child both write to an fd opened before the fork. Why do their writes interleave rather than overwrite each other? (They share one open file description, and so one file offset.)
  2. A multi-threaded program calls `fork()`. What survives in the child, and why is taking a lock there dangerous? (Only the calling thread is copied. A mutex held by another thread stays locked forever.)
  3. Why is `fork()` cheap for a 10 GB process, and when does it stop being cheap? (Page-table copying, and COW faults when either side writes.)

### A2. Process lifecycle; zombie and orphan processes
- **Reported.** "What's a zombie process? Can you kill a zombie process?" ([Glassdoor / IGotAnOffer](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet). "What is a zombie process?" ([coditioning 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`). A Prepfully coach also cites zombies.
- **Core points.**
  - A **zombie** has exited, but its parent hasn't called `wait()`. Only its process-table entry and exit status remain; it holds no memory. You cannot kill it because it is already dead. Fix the parent so it reaps on `SIGCHLD`, or kill the parent so init adopts the zombie and reaps it.
  - An **orphan** is a child whose parent died first. It is re-parented to PID 1 or to the nearest *subreaper* (`PR_SET_CHILD_SUBREAPER`).
  - The real risk of zombies is PID exhaustion (`kernel.pid_max`, or `pids.max` in a cgroup).
- **Follow-ups.**
  1. How do you find zombies and their parent? (`ps -eo pid,ppid,stat,cmd | awk '$3 ~ /Z/'`)
  2. A container keeps accumulating zombies. Why? (PID 1 inside the container is the app, which doesn't reap. Fix with `tini`, `--init`, or by reaping in the app.)
  3. What does `kill -9` on a zombie do? (Nothing.)

### A3. Signals
- **Reported.** One candidate was asked how a signal from the terminal user reaches a process, "in detail at the kernel level." Another lists "signals" with virtual memory and the MMU. ([Glassdoor](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet.)
- **Core points.**
  - **The Ctrl-C path.** The tty line discipline sees the INTR character and sends `SIGINT` to the terminal's *foreground process group*.
  - **Delivery.** The kernel marks the signal pending. It is delivered when the task next returns to user mode, unless the signal is blocked by the task's mask.
  - **Catchability.** `SIGKILL` and `SIGSTOP` cannot be caught or blocked. `SIGTERM` can be caught, which allows a graceful shutdown.
  - **Common in production:** `SIGHUP` (reload config), `SIGCHLD`, `SIGPIPE`, `SIGSEGV`.
- **Follow-ups.**
  1. Why doesn't `kill -9` kill a process in `D` state? (It is in an uninterruptible sleep in the kernel. The signal is handled only when the process wakes, except for `TASK_KILLABLE` waits.)
  2. How does `systemctl stop` shut a service down? (`SIGTERM`, then `SIGKILL` after `TimeoutStopSec`.) How do you make the shutdown graceful?
  3. What is async-signal-safe, and why can't you call `printf` or `malloc` in a handler?

### A4. File descriptors and inodes
- **Reported.** Inodes, file descriptors and directory structures are listed as filesystem topics ([dataford](https://dataford.io/interview-guides/meta/devops-engineer) `AG`, low confidence). The role of the VFS ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`). "File systems" appears in almost every report.
- **Core points.**
  - An fd is an index into the per-process fd table. It points to an *open file description* (offset and flags), which points to an inode.
  - An inode holds the metadata and block pointers, but **not the file name**. Directories map names to inode numbers.
  - `rm` calls `unlink()`, which removes a name. The data is freed only when the link count is 0 **and** no process still has the file open.
  - Inodes can run out (`df -i`) while there is still free space.
- **Follow-ups.**
  1. A service logs "Too many open files." How do you diagnose it? (`ls /proc/PID/fd | wc -l` against the `Max open files` line in `/proc/PID/limits`; look for a leak with `lsof -p`; `fs.file-max`.)
  2. Hard links vs symbolic links: which survives the target being deleted, and which can cross filesystems?
  3. How can you recover a deleted file that a process still has open? (`cp /proc/PID/fd/N /tmp/recovered`)

### A5. Virtual memory, paging, the page cache
- **Reported.**
  - "How is virtual memory managed on Linux?" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`). "How does virtual memory work?" ([coditioning 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`). The MMU ([Glassdoor](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).
  - 32- vs 64-bit, stack vs heap, paging vs swapping, `vmstat` fields ([bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design) `AG`, one candidate).
- **Core points.**
  - Each process has its own virtual address space. Page tables map it to physical memory; the MMU does the translation and the TLB caches it.
  - **Page faults.** A *minor* fault means the page is already in RAM and just gets mapped. A *major* fault needs a disk read.
  - **Lazy allocation.** Memory is allocated on demand, `fork()` uses COW, and overcommit lets allocations exceed RAM (`vm.overcommit_memory`).
  - **Memory measures.** VSZ is the virtual size, RSS is what's resident, and PSS splits shared pages proportionally.
  - **Free RAM becomes page cache.** That's why `free` shows a "free" figure near zero on a healthy box; read the `available` column instead.
- **Follow-ups.**
  1. `malloc(1 GB)` on a host with 512 MB free succeeds. Why? When does it fail, and how? (Overcommit; touching the pages faults them in; the OOM killer may follow.)
  2. How do you tell a host is thrashing? (`vmstat` `si`/`so` > 0 continuously; `pgmajfault` rising in `/proc/vmstat`; `/proc/pressure/memory`.)
  3. Stack vs heap: where does each live, what limits each (`ulimit -s` vs `brk`/`mmap`), and what does a stack overflow look like?

### A6. The OOM killer
- **Reported.** Kernel OOM killer behavior is listed as a memory topic ([dataford](https://dataford.io/interview-guides/meta/devops-engineer) `AG`, low confidence). It is the obvious follow-up to "crashes every five minutes" (B3).
- **Core points.**
  - It runs when reclaim can't satisfy an allocation. It picks the task with the highest `oom_score`, which is mostly driven by memory use and adjusted by `oom_score_adj` (−1000 to 1000). It logs `Out of memory: Killed process …` to `dmesg`.
  - Under cgroup v2, `memory.max` triggers an OOM *inside that cgroup only*; count kills via `memory.events` (`oom_kill`).
  - `memory.high` throttles the cgroup before that point.
  - **Meta angle.** Facebook engineers built PSI (pressure stall information) and `oomd`, a user-space OOM killer that acts on pressure. `systemd-oomd` descends from it. Mention this if it fits naturally.
- **Follow-ups.**
  1. The OOM killer killed the database, not the leaking process. Why might that happen, and how do you protect the database? (`OOMScoreAdjust=-1000` on the unit, or a separate cgroup with `memory.min`.)
  2. A cgroup OOM vs a global OOM: how do you tell which happened from the logs?
  3. Why act on memory *pressure* rather than wait for the kernel's OOM killer? (The kernel acts late, after the box has been thrashing for a while.)

### A7. cgroups and namespaces
- **Reported.** A Prepfully coach says it helps to mention cgroups and namespaces for containerization. Note the counterpoint: one 2025 onsite had "no Docker, Kubernetes" trivia ([RW](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) `CR-25`). Know the kernel primitives, not the tools built on them.
- **Core points.**
  - **cgroups** limit and account for resources. In v2 the controls are `cpu.max`, `cpu.weight`, `memory.max`/`memory.high`, `io.max`, `pids.max`, plus per-cgroup `*.pressure` files.
  - **Namespaces** isolate a process's view of the system: `pid`, `net`, `mnt`, `uts`, `ipc`, `user`, `cgroup`, `time`.
  - A container is namespaces + cgroups + capabilities/seccomp + a root filesystem.
- **Follow-ups.**
  1. Host metrics look idle, but the containerized service has bad latency. What do you check? (`cpu.stat` `nr_throttled`/`throttled_usec`. CFS quota throttling is a classic cause.)
  2. Limits vs weights: what happens to each when the host is idle?
  3. What is special about PID 1 in a PID namespace? (It reaps orphans, and it ignores signals it has no handler for.)

### A8. Scheduling and load average
- **Reported.** "How does the Linux kernel handle process scheduling and what algorithms are involved?" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`).
- **Core points.**
  - **The scheduler.** CFS was the default until EEVDF replaced it in Linux 6.6. It uses per-CPU run queues and nice values that map to weights.
  - **Load average** is an exponentially damped count of runnable (`R`) **plus uninterruptible (`D`)** tasks over 1, 5 and 15 minutes. Counting `D` tasks is Linux-specific, and it explains "high load, low CPU" (B7).
- **Follow-ups.**
  1. A load of 16 on a 16-core box: is that bad?
  2. How do you see the run-queue length right now? (The `r` column of `vmstat 1`.)
  3. What do `nice` and `ionice` actually change?

### A9. System calls, `strace` and tracing
- **Reported.** "How does strace work? How do you trace all the function calls in a running process? What does strace do and when would you use it?" ([Glassdoor / IGotAnOffer](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet). "System calls, tcpdump" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`).
- **Core points.**
  - `strace` uses `ptrace` and stops the tracee at every syscall, so it carries **large overhead**. Useful flags: `-f -tt -T -e trace=network,file -p PID`, and `-c` for a summary.
  - `ltrace` traces library calls.
  - For low overhead in production use `perf trace`, `perf record -g`, `bpftrace`, or BCC tools (`execsnoop`, `opensnoop`, `biolatency`, `tcpretrans`). For interpreted languages, `py-spy` and friends.
- **Follow-ups.**
  1. Why shouldn't you `strace` a hot production process for long? What do you use instead?
  2. `strace -c` shows 90% of the time in `futex`. What does that tell you? (Lock contention or idle worker threads. Look at threads with `-f`, then at the user-space stacks.)
  3. `connect()` takes exactly 1 s or 3 s. What does that suggest? (SYN retransmits: the initial RTO is 1 s, so there is packet loss or a full SYN queue on the server.)

### A10. IPC, the VFS, and durability
- **Reported.** "How does Linux handle inter-process communication (IPC) and what are some common mechanisms used?" and "What is the role of the virtual file system (VFS)?" ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`).
- **Core points.**
  - **IPC mechanisms:** pipes and FIFOs, Unix domain sockets, shared memory (`shm_open` + `mmap`), message queues, semaphores, `eventfd`, signals.
  - **The VFS** gives one API over ext4, XFS, NFS, procfs and others, using superblock, inode, dentry and file objects.
  - **`write()` is not durable.** It returns once the data is in the page cache; only `fsync()` guarantees it reached the disk.
- **Follow-ups.**
  1. Which IPC mechanism is fastest for large data, and why? (Shared memory: no copy through the kernel.)
  2. What happens when you write to a pipe whose reader has exited? (`SIGPIPE`, or `EPIPE` if the signal is ignored.)
  3. A machine loses power right after `write()` returns. Is the data safe? What about after `fsync()` on a disk with a volatile write cache?

### A11. Security fundamentals
- **Reported.** "Security fundamentals" was part of a 2025 onsite Linux round ([RW E4](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`).
- **Core points.** rwx permissions and the umask, setuid/setgid, sticky bits, capabilities (`CAP_NET_BIND_SERVICE` rather than running as root), sudo, SSH keys and certificates, the idea behind SELinux/AppArmor, and least privilege.
- **Follow-ups.**
  1. How can a non-root service bind to port 443?
  2. Why is a setuid shell script dangerous?
  3. A file has mode 777 but the user still can't read it. Why? (Missing `x` on a parent directory, an SELinux label, or the mount options.)

---

## B. Troubleshooting scenarios

Reported scenarios come first; `PR` items cover the scenarios you asked for.

### B1. "The website is down" → the disk is full
- **Sources.** "Uncle Bernie's Website is down" ([RW E4 screen, Mar 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`). [PracHub: website outage with disk full](https://prachub.com/interview-questions/troubleshoot-a-website-outage-with-disk-full) (a Meta technical screen, updated Mar 2026) `AG`.
- **Path.**
  1. Scope it. Is the site down for everyone? Check DNS, `curl -v`, and the load balancer.
  2. `systemctl status nginx`, then `journalctl -u nginx` and the error log. You find `No space left on device`.
  3. `df -h`, then `du -xh --max-depth=1 / | sort -h` to find what is using the space.
  4. Free space safely (old logs, cores, `/tmp`). Restart, and confirm the site is back.
  5. Long-term:
     - `logrotate` that tells the daemon to reopen its log (`postrotate` sends a signal), or `copytruncate`.
     - Alerts on disk use at 80% and 90%.
     - A separate `/var/log` partition.
     - Rate-limited logging.
- **The goalposts that typically move.**
  - **`df` says 100% but `du` adds up to far less.** → A deleted file is still held open (see B2).
  - **`df -h` shows free space, but writes still fail with `ENOSPC`.** → The filesystem is out of inodes. Check `df -i`, then find the directory holding millions of small files.
  - **Root can write but the app can't.** → ext4 reserves about 5% of blocks for root (`tune2fs -l`, `-m`).
- **Follow-ups.**
  1. How do you free the space *without* restarting the service?
  2. You `rm`'d the 40 GB log, but `df` didn't change. Why not?
  3. How do you stop this happening again across 100,000 hosts?

### B2. Disk full, despite deleted files (`PR`, the standard follow-up to B1)
- **Diagnose.** `lsof +L1` lists open files whose link count is below 1, meaning deleted files that are still open. Alternatively, `find /proc/*/fd -lname '*(deleted)'`.
- **Fix.**
  - Restart or reload the process that holds the file. If you can't, truncate it in place: `: > /proc/PID/fd/N`.
  - Root cause: someone ran `rm` on a live log instead of rotating it.
- **Follow-ups.**
  1. Why does truncating through `/proc/PID/fd` work when `rm` didn't?
  2. After the truncation, the process keeps writing at its old offset. What happens to the file? (It becomes sparse, unless the file was opened with `O_APPEND`.)
  3. How would logrotate's `copytruncate` vs `create` + a signal handle this?

### B3. Failing deployments or CI/CD
- **Sources.** [RW Prep to Offer screen](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) `CR-25`. [1point3acres 1130439, 2025](https://www.1point3acres.com/interview/thread/1130439) (login required). A Glassdoor report of a "service deployment failure, temporary fix followed by a long-term fix" (snippet).
- **Path.**
  1. **Stop the bleeding.** Halt the rollout or roll back.
  2. **Ask what changed:** the code, the config, a dependency, the base image, or a secret.
  3. **Read the evidence:** `systemctl status`, `journalctl -u svc -b --since "10 min ago"`, and the exit code (`203/EXEC` means the binary is missing or not executable; `127` means command not found).
  4. **Check the usual causes:**
     - Port already in use: `ss -ltnp 'sport = :8080'`.
     - Permissions or an SELinux label.
     - A missing environment variable or secret.
     - A dependency is unreachable (DB, DNS).
     - The deploy directory's disk is full.
     - The health check fails, so the load balancer pulls the host.
- **Follow-ups.**
  1. The deploy succeeded on 95% of hosts. How do you find out what is different about the other 5%? (Hardware or kernel generation, rack or region, a stale config, a full disk.)
  2. The release included a database schema migration. Can you still roll back safely? (Expand/contract migrations.)
  3. What would you automate so a human never debugs this by hand again?

### B4. A server crashes every five minutes and restarts automatically
- **Sources.** [coditioning, Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.
- **Hypotheses.**
  - **The OOM killer.** `dmesg -T | grep -i oom`, and `memory.events` if it runs in a cgroup.
  - **Killed for missing a health check.** A systemd watchdog (`WatchdogSec`) or a liveness probe is killing it.
  - **Something scheduled.** A cron job or timer on `*/5`.
  - **A segfault.** Check `coredumpctl list`.
  - **Telling them apart.** `journalctl -u svc` reads `status=9/KILL` for a kill and `dumped core` for a crash.
- **Follow-ups.**
  1. How do you tell an OOM kill apart from a health-check kill using only the logs?
  2. How do you capture a heap profile or core dump *before* the next crash?
  3. Restarting hides the problem. When is auto-restart the right call anyway?

### B5. Slow web server, but CPU, memory and disk all look normal
- **Sources.** [coditioning, Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.
- **Break the time down first.** `curl -w '%{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total}\n'`.
- **Hypotheses.**
  - **It's waiting on something downstream:** the database, an external API, or a per-request DNS lookup. Resolver timeouts default to 5 s, so latency clusters at multiples of 5 s.
  - **Pools are exhausted:** threads or connections.
  - **The accept queue is overflowing:** `nstat -az TcpExtListenOverflows`; for a `LISTEN` socket in `ss -lnt`, Recv-Q is the current queue and Send-Q is the backlog limit.
  - **fd limits**, or **lock contention** (`strace -c -f -p`).
  - **GC pauses.**
  - **Packet loss:** `nstat TcpRetransSegs`, `ss -ti`.
  - **cgroup CPU throttling**, which host-level metrics don't show.
- **Follow-ups.**
  1. Only p99 is slow; p50 is fine. What changes in your search?
  2. Only users in one region see it.
  3. It started right after a deploy, but the diff looks harmless.

### B6. "The site goes down often. We've given you the standard metrics. What else would you gather?"
- **Sources.** LeetCode PE new-grad thread, [6805017](https://leetcode.com/discuss/post/6805017/) (snippet) `CR-25`.
- **What to gather.**
  - Logs whose timestamps line up with each outage.
  - `dmesg` (OOM kills, NIC resets, disk errors).
  - Per-process RSS, fd count, thread count; TCP socket states (`ss -s`, TIME_WAIT counts).
  - GC logs; the deploy and config change log; cron and timer schedules.
  - The health of upstream dependencies.
  - Synthetic probes from several vantage points; PSI; core dumps.
- **Follow-ups.**
  1. It goes down at :00 every hour. (cron, log rotation, batch jobs, certificate reloads.)
  2. How do you capture the system's state *at the moment* it fails? (A trigger script, a `perf` ring buffer, an `atop` history.)
  3. Which of these signals would you turn into an alert, and at what threshold?

### B7. High load average, low CPU (`PR`)
- **Reasoning.** Load counts `D`-state tasks (A8), so something is blocked on I/O: NFS, a dying disk, or a stuck block device.
- **Commands.**
  - `vmstat 1`: the `b` and `wa` columns.
  - `ps -eo state,pid,wchan:32,cmd | awk '$1=="D"'`, and `cat /proc/PID/stack` as root.
  - `iostat -xz 1`: `r_await`/`w_await` and `aqu-sz`.
  - `dmesg | grep -i 'i/o error'`, `mount | grep nfs`, and `/proc/pressure/io`.
- **Follow-ups.**
  1. Why does Linux count `D` state in load at all?
  2. Can you kill those processes? What do you do with an NFS server that is hung behind a `hard` mount?
  3. `%util` is 100% on an NVMe drive. Is the drive saturated? (Not necessarily. NVMe serves many requests in parallel, so look at latency and queue depth instead.)

### B8. High CPU, low disk I/O; or "the system is unresponsive"
- **Sources.** "How would you diagnose a system that's high in CPU usage but low in disk I/O?" and "You receive a report that a system is unresponsive, what do you do?" ([Glassdoor / IGotAnOffer](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).
- **Split the CPU time first** with `mpstat -P ALL 1`:
  - **`us` high:** profile it. `pidstat 1`, `perf top`, `perf record -g` plus a flame graph.
  - **`sy` high:** a syscall storm. Use `strace -c`.
  - **`si` high:** network softirq. Check `/proc/softirqs`, IRQ affinity, RPS.
  - **`st` high:** a noisy neighbor on the hypervisor.
- **If the box is unresponsive:**
  - Use the console or IPMI if SSH hangs.
  - Check for memory thrashing, a fork bomb (`pids`), a storm of `D`-state tasks, or soft lockups in `dmesg`.
  - Magic SysRq (`echo t > /proc/sysrq-trigger` dumps every task).
- **Follow-ups.**
  1. One core is at 100% and the rest are idle.
  2. CPU is high but throughput is low. (Spinlocks, contention, a retry storm.)
  3. How do you keep `sshd` reachable on a box under memory pressure? (Its own cgroup, `OOMScoreAdjust`.)

### B9. Which process is using the most memory?
- **Sources.** "How do you find which process is using the most memory on Linux?" ([Glassdoor / IGotAnOffer](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).
- **Answer.**
  - Rank by resident memory: `ps aux --sort=-rss | head`, or `top` and press `M`.
  - Use PSS for shared pages: `smem`, or `/proc/PID/smaps_rollup`.
  - Don't forget memory that no process owns: slab (`slabtop`), tmpfs and `/dev/shm`, the page cache, hugepages.
- **Follow-ups.**
  1. The RSS of all processes adds up to more than total RAM. How? (Shared pages are counted once per process.)
  2. `free` shows little free memory and no process is large. Where did the memory go?
  3. Memory grows 1% per hour. How do you find the leak in production?

### B10. Debugging a slow network path or slow syscalls with `strace`, `tcpdump` and `perf` (`PR`; the tools are reported in [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer))
- **Workflow.**
  1. `strace -f -tt -T -e trace=network -p PID` shows where the wall-clock time goes (`connect`, `poll`, `recvfrom`).
  2. `tcpdump -i any -nn -s0 'host X and port 443' -w cap.pcap` captures the traffic. Look for retransmits, zero windows, RSTs, and a gap between the SYN and the SYN-ACK.
  3. `perf trace`, or `perf record -g -p PID` then `perf report`, for lower overhead.
  4. BCC tools: `tcpconnlat`, `tcpretrans`, `biolatency`.
- **Follow-ups.**
  1. `strace` shows `poll()` blocking for 5 s. What do you look at next? (Which fd it is, and what is on the other end.)
  2. Only *large* responses stall. (An MTU problem or a PMTUD black hole: ICMP "frag needed" is being dropped.)
  3. How do you do all this safely on a production host? (Bounded captures, BPF filters, eBPF instead of `ptrace`.)

---

## C. "Explain this output" cheat sheet

Reported: "explain the output of specific Linux commands" ([Bala](https://bala-krishnan.com/posts/18-meta/)); `vmstat` fields ([bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design)); `vmstat` and `netcat` ([Glassdoor](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm), snippet).

| Command | What to be able to explain |
|---|---|
| `uptime` / `top` header | 1/5/15-minute load (includes `D` tasks); `us sy ni id wa hi si st`; `VIRT RES SHR`; the `S` column |
| `vmstat 1` | `r` (runnable), `b` (blocked), `swpd free buff cache`, `si so` (swap in/out), `bi bo` (block I/O), `in cs` (interrupts, context switches), `us sy id wa st` |
| `free -m` | Why `available` matters more than `free`; `buff/cache` |
| `iostat -xz 1` | `r/s w/s`, `r_await w_await` (ms), `aqu-sz`; why `%util` misleads on SSDs and NVMe |
| `ss -tinp` / `ss -s` | Socket states; Recv-Q/Send-Q (meaning differs for `LISTEN` sockets); `rtt`, `cwnd`, `retrans` |
| `ps -eo pid,ppid,stat,rss,cmd` | `STAT` codes `R S D Z T I`, and the `<`, `N`, `s`, `l`, `+` modifiers |
| `dmesg -T` | OOM-killer reports, I/O errors, NIC link flaps, soft lockups |
| `nc -zv host port` / `nc -l` | Checking that a port is reachable; a quick listener; testing through a firewall |
| `ls -l foo*` | The *shell* expands the glob before `ls` runs; what happens when nothing matches ([bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design)) |

**The 60-second triage sequence.** A 2024 candidate recommended Brendan Gregg's [Linux Performance Analysis in 60,000 Milliseconds](https://netflixtechblog.com/linux-performance-analysis-in-60-000-milliseconds-accc10403c55):
`uptime` → `dmesg | tail` → `vmstat 1` → `mpstat -P ALL 1` → `pidstat 1` → `iostat -xz 1` → `free -m` → `sar -n DEV 1` → `sar -n TCP,ETCP 1` → `top`.

**Quick-fire questions (OA and recruiter-call style, `PR` based on reported topics).**
- The online quiz is about 20 multiple-choice questions in about 18–20 minutes, covering Linux commands, OS concepts and networking ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer); Glassdoor, snippet).
- One recruiter call asked "a Linux command to synchronize two servers" (`rsync -avz --delete`, with `-n` for a dry run) ([LeetCode 2043600](https://leetcode.com/discuss/post/2043600/meta-recruiter-phone-call-production-engineer-questions/), snippet, `CR-old`).
- Also drill these:
  - `find` by size and mtime; numeric `chmod`.
  - `grep -r`; `sed -i`; selecting fields with `awk`.
  - `tar`; `lsof -i :80`; `kill -l`; `nohup` vs `disown`.
  - The contents of `/proc/PID/`.

---

## D. Prep resources candidates actually cited

- **Books.**
  - Brendan Gregg, *Systems Performance*.
  - *Operating Systems: Three Easy Pieces* (OSTEP).
  - Tanenbaum, *Modern Operating Systems*, chapter 10 (the Linux case study).
  - Sources: both [RW posts](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview).
- **More books.** Michael Kerrisk, *The Linux Programming Interface* ([Bala](https://bala-krishnan.com/posts/18-meta/)). Robert Love, *Linux Kernel Development*, and *Advanced Linux Programming* ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer)).
- **Practice format.** Do mock troubleshooting with a partner who *invents* each command's output and changes the facts mid-way. This mirrors the "moving goalposts" format. One candidate used 10 paid mocks with an ex-Meta PE ([RW Prep to Offer](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta)).

## E. Checking these threads yourself

- **Reddit** (I couldn't reach it). Search these in your browser:
  - `site:reddit.com meta "production engineer" troubleshooting round`
  - `site:reddit.com/r/sre "production engineer" meta linux interview`
- **Blind.** Threads asking what the PE troubleshooting round covers: [meta production engineering interview](https://www.teamblind.com/post/meta-production-engineering-interview-r7vvsrui), [production engineer at Meta interview](https://www.teamblind.com/post/production-engineer-at-meta-interview-nvxekyue).
- **1point3acres** (login required): [Linux troubleshooting phone screen, Jan–Mar 2025](https://www.1point3acres.com/interview/thread/1112020); [PE phone screen, Jan–Mar 2026](https://www.1point3acres.com/interview/thread/1162101).
