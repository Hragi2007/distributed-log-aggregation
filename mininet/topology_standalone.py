from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
#this is not the final topology, it is just a good test topology to test if mininet is working. final topology will be built after seeing udp clients and servers and sdn controller files.
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

def run():
    topo = LogAggregationTopology()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True
    )

    try:
        net.start()

        # Put switches into standalone mode for basic connectivity testing.
        for switch in net.switches:
            switch.cmd('ovs-vsctl set-fail-mode', switch.name, 'standalone')

        print("\nThree log clients: h1, h2, h3")
        print("Central log server: h4")
        print("Potential bottleneck: s1 <-> s2\n")

        CLI(net)

    finally:
        net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
