from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
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
        self.addLink(s1, s2, bw=0.1, max_queue_size=20)


def run():
    topo = LogAggregationTopology()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    try:
        net.start()

        for switch in net.switches:
            switch.cmd('ovs-vsctl set-fail-mode', switch.name, 'standalone')

        print("\nBottleneck: s1 <-> s2 limited to 0.1 Mbps, queue 20 packets\n")

        CLI(net)

    finally:
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
