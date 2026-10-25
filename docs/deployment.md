# Deployment

How StockBoard is hosted and how to set it up again. Addresses, keys and account names are left out because the repository is public.

## Stack

| Part | What |
|---|---|
| Server | Oracle Cloud Always Free VM (`VM.Standard.E2.1.Micro`, 1 GB memory), Ubuntu 24.04 LTS |
| App | `uvicorn` running `stockboard_backend.web_server:app`, started by systemd |
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
   git clone <repository url> ~/StockBoard && cd ~/StockBoard
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```

4. **Run it as a service.** Create `/etc/systemd/system/stockboard.service`:

   ```ini
   [Unit]
   Description=StockBoard web server
   After=network-online.target
   Wants=network-online.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/StockBoard
   ExecStart=/home/ubuntu/StockBoard/.venv/bin/python -m uvicorn stockboard_backend.web_server:app --host 127.0.0.1 --port 8000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload && sudo systemctl enable --now stockboard
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
systemctl status stockboard
journalctl -u stockboard -f
cd ~/StockBoard && git pull && sudo systemctl restart stockboard
```

After `requirements.txt` changes run `~/StockBoard/.venv/bin/pip install -r requirements.txt`, then restart the service. Turn the public address off with `sudo tailscale funnel --https=443 off`.

## Security notes

- The page has no login. Anyone with the address can open it and call the read-only API.
- The SSH private key is the only way in; passwords are off. Never put it in the repository or a synced folder.
- Keep port 22 closed to the internet. Scanners fill sshd's unauthenticated connection slots (`MaxStartups`) and logins then fail at random.
- If Tailscale stops working there is no SSH route. Use the Oracle console (Cloud Shell or the serial console) to recover.
- Back up `/etc/iptables/rules.v4` before editing it. Add a new rule live first, test it, then write it to the file.
- Oracle may reclaim Always Free instances that stay idle, so keep the instance in use.
