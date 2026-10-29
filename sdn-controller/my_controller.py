

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4

# DSCP values used by log_client.py
CRITICAL_DSCP = 46
ERROR_DSCP = 26

# Higher number means higher flow priority
CRITICAL_FLOW_PRIORITY = 300
ERROR_FLOW_PRIORITY = 200
DEFAULT_FLOW_PRIORITY = 1

class MyController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        print("My SDN Controller has started!")

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Send unmatched packets to the controller
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]

        self.add_flow(datapath, 0, match, actions)
        print("Switch connected; table-miss rule installed.")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst
        dpid = datapath.id

        # Learn the source MAC address
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        dscp = None
        queue_id = 0
        priority = DEFAULT_FLOW_PRIORITY

        # Classify IP packets using DSCP
        if ip_pkt is not None:
            dscp = ip_pkt.tos >> 2
            print(
                "Packet received: switch =", dpid,
                "source =", src, "destination =", dst,
                "DSCP =", dscp,
            )

            if dscp == CRITICAL_DSCP:
                priority = CRITICAL_FLOW_PRIORITY
                queue_id = 1
                print("CRITICAL traffic: priority 300, queue 1")

            elif dscp == ERROR_DSCP:
                priority = ERROR_FLOW_PRIORITY
                queue_id = 0
                print("ERROR traffic: priority 200, queue 0")

        # Use the learned destination port, or flood if unknown
        out_port = self.mac_to_port[dpid].get(
            dst, ofproto.OFPP_FLOOD
        )

        actions = []

        if ip_pkt is not None:
            actions.append(parser.OFPActionSetQueue(queue_id))

        actions.append(parser.OFPActionOutput(out_port))

        # Install a flow only when the destination is known
        if out_port != ofproto.OFPP_FLOOD:
            if ip_pkt is not None:
                match = parser.OFPMatch(
                    in_port=in_port,
                    eth_type=ether_types.ETH_TYPE_IP,
                    eth_dst=dst,
                    ip_dscp=dscp,
                )
            else:
                match = parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                )

            self.add_flow(
                datapath,
                priority,
                match,
                actions,
            )

        # Forward this packet immediately, including unknown destinations
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
