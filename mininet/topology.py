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

        print("\nThree log clients: h1, h2, h3")
        print("Central log server: h4")
        print("Switches s1 and s2 should connect to Ryu.\n")

        CLI(net)

    finally:
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
