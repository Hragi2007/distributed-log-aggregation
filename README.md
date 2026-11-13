# Project 10: Distributed Log Aggregation System

**Live results page:** https://hragi2007.github.io/distributed-log-aggregation/

A Mininet and SDN project for PES University. Several hosts send application logs over UDP to one central server. The network has a bottleneck link, and an SDN controller (Ryu) classifies critical logs by their DSCP tag so the switch can give them a priority queue when the link is congested. The project measures whether that priority reduces the delay of critical logs under congestion, and what it costs the other logs.

## Team and Contributions

| Name | SRN | Contribution |
|---|---|---|
| Goutami Velaga | PES1UG25CS191 | SDN controller (`sdn-controller/my_controller.py`) and DSCP-based classification. Designed the QoS queue setup on the bottleneck ports (queue 0 at 2 Mbps, queue 1 at 8 Mbps). Ran the congestion tests and the critical versus default latency measurements with iperf and ping. |
| Jahnavi S | PES1UG25CS217 | UDP log client and server (`udp-app/log_client.py`, `udp-app/log_server.py`): message format with timestamps, sequence numbers and severity; marks critical logs with DSCP so the controller can classify them; per-severity reporting of packet loss and delivery time. |
| Harshith Ragi | PES1UG25CS203 | Mininet topology (`mininet/topology.py`, `mininet/topology_standalone.py`). Integrated Goutami's QoS queue setup into the topology so it runs automatically. Reproduced her congestion and latency tests on a separate VM. Ran the UDP log measurements under congestion and the baseline without the controller. Assembled the results and evidence, and made a small fix to the controller's rule for non-IP traffic. |

The congestion setup and its first measurements were designed and run by Goutami. Harshith's runs reproduce those results and add the UDP log measurements, which her tests did not cover.

## Architecture

```
h1 ──┐
h2 ──┼── s1 ════ s2 ── h4
h3 ──┘     bottleneck
```

- **h1, h2, h3:** log clients. Each runs `log_client.py` and sends logs over UDP to port 5140.
- **h4:** central log server. Runs `log_server.py`, receives all logs, and writes a per-host, per-severity report.
- **s1, s2:** Open vSwitch switches. All client traffic crosses the s1-s2 link to reach h4, so that link is the bottleneck.
- **s1-s2 link (`s1-eth4` and `s2-eth1`):** rate-limited by two QoS queues (see Queue setup).
- **Ryu controller (`my_controller.py`):** connects to both switches on `127.0.0.1:6653` using OpenFlow 1.3. It reads each packet's DSCP tag and installs a flow rule that sets the queue and priority.

**Message flow:** a client builds a JSON log (`type`, `host`, `seq`, `sev`, `ts`, `msg`), marks CRITICAL and ERROR logs in the IP header, and sends it. The packet crosses s1, the bottleneck, and s2 to h4. Each client ends with a FIN message containing its send counts, so the server can calculate exact loss.

## How Classification Works

The controller reads the DSCP value in each IP packet:

| Severity | DSCP | Flow priority | Queue |
|---|---|---|---|
| CRITICAL | 46 (`nw_tos=184`) | 300 | 1 |
| ERROR | 26 (`nw_tos=104`) | 200 | 0 |
| All others | 0 | 1 | 0 |

A flow rule that matches a critical packet's DSCP value and sends it to queue 1 is installed on the switch. You can see it with:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1 | grep nw_tos=184
```

## Queue Setup

The bottleneck ports use Open vSwitch's `linux-htb` QoS, with a 10 Mbps port limit:

- **Queue 0** (default and error traffic): 2 Mbps minimum and maximum.
- **Queue 1** (critical traffic): 8 Mbps minimum and maximum.

The queues are created by `setup_queues()` in `mininet/topology.py` when the network starts. The same queue setup is applied in `topology_standalone.py` for the baseline, so the only difference between the two runs is the controller.

## Environment

- Ubuntu VM running in VirtualBox
- Mininet with Open vSwitch
- iperf for the background load
- Ryu 4.34, installed in a separate Python 3.9 virtual environment (`~/ryu-venv`), because Ryu does not build on newer Python versions

Install Ryu:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv venv --python 3.9 ~/ryu-venv
source ~/ryu-venv/bin/activate
uv pip install "setuptools==67.6.1" "eventlet==0.30.2" wheel pbr
uv pip install --no-build-isolation ryu
```

## How to Run

Use two terminals. Terminal 1 runs Ryu, and terminal 2 runs Mininet. Never run `sudo mn -c` while Ryu is running, because it stops Ryu.

### Controller run (with prioritisation)

**Terminal 1 (Ryu):**

```bash
cd ~/distributed-log-aggregation && source ~/ryu-venv/bin/activate
ryu-manager sdn-controller/my_controller.py
```

Wait for `My SDN Controller has started!`.

**Terminal 2 (Mininet):**

```bash
sudo mn -c
sudo python3 mininet/topology.py
```

Ryu should print `Switch connected; table-miss rule installed.` twice.

At the `mininet>` prompt, run each command once and in this order:

```text
h4 iperf -s -u -p 5001 &
h4 python3 udp-app/log_server.py --idle-exit 10 --out results/final_sdn > results/server_final_sdn.txt 2>&1 &
h1 iperf -c 10.0.0.4 -u -p 5001 -b 12M -t 60 &
py [h.cmd('python3 udp-app/log_client.py --server 10.0.0.4 --name=%s --count 1500 --rate 50 > /dev/null 2>&1 &' % h.name) for h in (h1, h2, h3)]
```

Wait about 40 seconds, then:

```text
h4 cat results/server_final_sdn.txt
```

### Baseline run (no controller)

Stop Ryu (`Ctrl+C`), then in terminal 2:

```bash
exit
sudo mn -c
sudo python3 mininet/topology_standalone.py
```

Run the same four commands as above, with `--out results/baseline_clean` in the server command and the output file renamed to match. Wait about 60 seconds, then:

```text
h4 cat results/server_baseline_clean.txt
```

### Latency check (optional, controller run)

While the load from h1 is running, send pings from h2:

```text
h2 ping -Q 0xb8 -c 30 -i 0.2 10.0.0.4
h2 ping -Q 0x68 -c 30 -i 0.2 10.0.0.4
h2 ping -c 30 -i 0.2 10.0.0.4
```

The first is critical, the second is error, and the third is default traffic.

## Results

All runs used the same 12 Mbps UDP load from h1, the same log clients (1,500 logs per host at 50 logs/s), and the same 10 Mbps bottleneck with queues.

### UDP logs: controller versus baseline

Measured per host and severity by the log server. Loss was 0% in every row of both runs.

| Severity | Controller run (avg delay) | Baseline run (avg delay) |
|---|---|---|
| CRITICAL | 0.25 to 18.66 ms | 455 to 463 ms |
| ERROR | 449 to 456 ms | 443 to 467 ms |
| DEBUG, INFO, WARNING | 448 to 467 ms | 454 to 464 ms |

The controller run's critical delay is much lower than every other severity, and lower than the baseline's critical delay. Its other severities look the same as the baseline's. The full per-host tables are in `docs/evidence/final_sdn_stats.csv` and `docs/evidence/baseline_clean_stats.csv`.

### Latency pings under congestion (controller run)

Each row is an average of 30 pings from h2, with 0% loss.

| Traffic | Average RTT |
|---|---|
| Critical (`-Q 0xb8`) | 9.8 ms |
| Error (`-Q 0x68`) | 426 ms |
| Default | 423 ms |

Without load, pings averaged about 0.05 ms, so the delay only appears under congestion.

### Flow rule and queue checks

The `priority=300` rule with `set_queue:1` is installed on s1, and queue 1 receives the critical packets. Queue 0 is held near its 2 Mbps limit during the load.

## Evidence

The `docs/evidence/` folder holds the screenshots and CSVs. Screenshots 1 to 15 are from Goutami's run. Screenshots 16 to 19 and the two CSVs are from Harshith's reproduction.

**Goutami's run (1 to 15):**

1. Controller reading DSCP values and assigning queues and priority
2. Default traffic limited to queue 0's 2 Mbps
3. Packets increasing in queue 0 when default traffic is sent
4. Critical traffic sent along with default traffic
5. Packets increasing in queue 1 when critical traffic is sent
6. Critical logs sent a second time
7. Packets in queue 1 rising from 6 to 14 on the second send
8. 90-second traffic run to measure latency
9. Critical latency is very low under congestion
10. Error latency is high under congestion
11. Critical traffic without congestion
12. Error traffic without congestion
13. Second congestion test, critical results
14. Second congestion test, error results
15. Flow rules installed on s1 and s2

**Harshith's reproduction (16 to 19 and CSVs):**

16. `16)udp_run_final_udp_report.png`: UDP log report, controller run
17. `17)udp_run_topology_and_udp_start.png`: topology startup and UDP run start
18. `18)udp_run_ryu_classification.png`: Ryu classifying critical and error traffic
19. Baseline UDP log report, no controller
- `final_sdn_stats.csv`: controller run results
- `baseline_clean_stats.csv`: baseline results

## Scope and Notes

- **Measured conditions:** the controller and baseline runs use the same topology, the same QoS queues on the bottleneck, the same 12 Mbps iperf load from h1, and the same log clients (1,500 logs per host at 50 logs/s). The only difference is the controller.
- **Emulated network:** all hosts and switches run as Mininet emulation on one VM. Delay values describe this setup and can vary slightly between runs.
- **Critical-log average:** h2's critical logs averaged 18.66 ms, higher than h1 and h3 (about 0.3 ms), because h2 also sent the ping tests during the run.
