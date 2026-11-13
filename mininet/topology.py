from functools import partial
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel


class LogAggregationTopology(Topo):
    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s2)
        self.addLink(s1, s2)


def setup_queues(net):
    queue_cmd = (
        '-- --id=@newqos create QoS type=linux-htb other-config:max-rate=10000000 '
        'queues:0=@q0 queues:1=@q1 -- '
        '--id=@q0 create Queue other-config:min-rate=2000000 other-config:max-rate=2000000 -- '
        '--id=@q1 create Queue other-config:min-rate=8000000 other-config:max-rate=8000000'
    )
    for switch, port in [('s1', 's1-eth4'), ('s2', 's2-eth1')]:
        net.get(switch).cmd('ovs-vsctl set Port', port, 'qos=@newqos', queue_cmd)


def run():
    topo = LogAggregationTopology()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=partial(OVSSwitch, protocols='OpenFlow13'),
        autoSetMacs=True
    )

    net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6653
    )

    try:
        net.start()
        setup_queues(net)

        print("\nThree log clients: h1, h2, h3")
        print("Central log server: h4")
        print("QoS queues on s1-eth4 and s2-eth1: queue 0 = 2 Mbps, queue 1 = 8 Mbps")
        print("Switches s1 and s2 should connect to Ryu.\n")

        CLI(net)

    finally:
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
