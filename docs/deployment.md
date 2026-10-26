# Deployment

How Stock Benchmark is hosted and how to set it up again. Addresses, keys and account names are left out because the repository is public.

## Stack

| Part | What |
|---|---|
| Server | Oracle Cloud Always Free VM (`VM.Standard.E2.1.Micro`, 1 GB memory), Ubuntu 24.04 LTS |
| App | `uvicorn` running `stock_benchmark_backend.web_server:app`, started by systemd |
| Admin access | SSH over Tailscale only |
| Public address | Tailscale Funnel: `https://<server name>.<tailnet name>.ts.net`, HTTPS certificate included |

```
browser --HTTPS--> Tailscale Funnel --> uvicorn on 127.0.0.1:8000
you     --SSH----> Tailscale -------> port 22 (tailscale0 only)
```

Funnel needs no domain, no inbound port and hides the server's own IP. It only serves the tailnet's `ts.net` name, on ports 443, 8443 and 10000. A custom domain needs a reverse proxy such as Caddy or Cloudflare Tunnel instead.

## Set up

1. **Create the VM.** In the Oracle console create an instance: Ubuntu 24.04 (x86_64 image for the Micro shape), a public subnet with a public IPv4 address, and an SSH key pair. Keep the private key in `~/.ssh` with mode `400`.
2. **Prepare the system.**

   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip git
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

   Swap matters on a 1 GB machine.
3. **Install the app.**

   ```bash
   git clone <repository url> ~/stock-benchmark && cd ~/stock-benchmark
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```

4. **Run it as a service.** Create `/etc/systemd/system/stock-benchmark.service`:

   ```ini
   [Unit]
   Description=Stock Benchmark web server
   After=network-online.target
   Wants=network-online.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/stock-benchmark
   ExecStart=/home/ubuntu/stock-benchmark/.venv/bin/python -m uvicorn stock_benchmark_backend.web_server:app --host 127.0.0.1 --port 8000
   Restart=always
   RestartSec=5
   MemoryHigh=300M
   MemoryMax=400M
   MemorySwapMax=64M
   TasksMax=96
   CPUWeight=50

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload && sudo systemctl enable --now stock-benchmark
   ```

5. **Join Tailscale.**

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --hostname=<server name>
   ```

   Install Tailscale on the laptop and phone too, signed in to the same account, then SSH to the server's Tailscale address.
6. **Close SSH to the internet.** Oracle's Ubuntu image allows port 22 from anywhere. Allow it on the Tailscale interface only, then save the rules:

   ```bash
   sudo iptables -I INPUT 5 -i tailscale0 -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT
   sudo iptables -D INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT
   ```

   Then make the same change in `/etc/iptables/rules.v4`. Leave the `InstanceServices` rules alone. Also remove the port 22 ingress rule from the Oracle security list. Test a Tailscale SSH login before closing the old route.
7. **Publish with Funnel.** In the Tailscale admin console turn on HTTPS certificates and Funnel for the server, then:

   ```bash
   sudo tailscale funnel --bg 8000
   ```

   The setting survives reboots. Use `tailscale serve` instead of `tailscale funnel` for a page that only devices in the tailnet can open.

## Operate

```bash
systemctl status stock-benchmark
journalctl -u stock-benchmark -f
cd ~/stock-benchmark && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart stock-benchmark
```

The fetch cache lives in memory, so the first refresh after a restart asks every source once (about 180 requests, most of them Yahoo); later refreshes during market hours make about 70. The log prints a line every hour with the Yahoo request counts and any rate-limit or error answers: watch it for 429 and 401 after a change.

After `requirements.txt` changes run `~/stock-benchmark/.venv/bin/pip install -r requirements.txt`, then restart the service. Turn the public address off with `sudo tailscale funnel --https=443 off`.

## Hardening: what and why

The page is public and has no login. The aim is that the *website* may fail and be restarted, while the *server* (SSH, Tailscale) never goes down.

1. **Snapshot cache** (`web_server.py`). The dashboard reads one JSON snapshot that changes at most every 10 minutes, yet every request used to re-read and re-parse it, the main repeated cost on a 1/8-core machine. The snapshot is now parsed once and kept until the refresher replaces the file. The cache key is the file's identity (path, inode, modification time, size), not a timer, so data is never older than the file and nothing a visitor sends can grow the cache. It is one tuple swapped in a single assignment, so it needs no lock and no endpoint changes.
2. **Global request limit** (`request_limiter.py`, `max_requests_per_second` in `config/settings.yaml`). A cache lowers the cost of a request, not their number. One token bucket for the whole server turns a flood into cheap `429` replies before any route runs. `0` turns it off; raise it on a bigger machine. It is global and not per visitor because behind Funnel the app may not see the real client address, so a per-visitor table could silently fail or be bypassed with a spoofed header. Known limit: one heavy user can use up the shared budget until they stop. Fixing that needs the real client address or a service in front, such as Cloudflare.
3. **systemd resource limits** (the five lines in the unit file). If the app misbehaves, only the app should be hurt. A memory cap makes the kernel stop the *service*, not `sshd` or `tailscaled`. A swap cap stops a slow-disk spiral on a machine with 1/8 of a CPU. `CPUWeight` lets `sshd` and `tailscaled` win when the CPU is contended. `Restart=always` brings the site back in seconds, and the snapshot is on disk, so nothing is lost. The limits live on the server, not in the code, so a bigger machine only needs new numbers.

### How the numbers were chosen

A sizing method that works on any machine:

1. Measure memory used by everything except the app (`free -m`, `ps`).
2. Measure the app's idle size and its peak during one refresh: run `python -m stock_benchmark_backend.refresh_scheduler --once` and read the child's maximum resident size (`/usr/bin/time -v`, or `resource.getrusage` in a small wrapper).
3. Take the cap from several independent estimates and use their median: the free-memory budget, the app's peak × 1.3 to 1.5, how much the kernel needs left for `sshd` and `tailscaled`, and the platform's limits. Estimates that rest on the same evidence count once.
4. Lean low when estimates disagree, and never exceed a ceiling that leaves room for SSH. If the refresh peak does not fit under the ceiling, reduce the refresh work instead of raising the cap.

Rules of thumb: `MemoryMax` ≈ 40% of RAM, `MemoryHigh` ≈ 75% of `MemoryMax`, `MemorySwapMax` ≈ 6% of RAM, `TasksMax` about three times the usual thread count. On the 1 GB machine used here that gives 400 MB, 300 MB and 64 MB.

If something breaks: `sudo systemctl restart stock-benchmark`, then `journalctl -u stock-benchmark -n 50`. If the whole machine hangs, reboot the instance from the Oracle console.

## Security notes

- The page has no login. Anyone with the address can open it and call the read-only API.
- The SSH private key is the only way in; passwords are off. Never put it in the repository or a synced folder.
- Keep port 22 closed to the internet. Scanners fill sshd's unauthenticated connection slots (`MaxStartups`) and logins then fail at random.
- If Tailscale stops working there is no SSH route. Use the Oracle console (Cloud Shell or the serial console) to recover.
- Back up `/etc/iptables/rules.v4` before editing it. Add a new rule live first, test it, then write it to the file.
- Oracle may reclaim Always Free instances that stay idle, so keep the instance in use.
