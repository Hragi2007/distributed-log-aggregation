
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types,ipv4
# DSCP values set by the UDP log client
CRITICAL_DSCP = 46
ERROR_DSCP = 26

# Higher flow priority means the rule is preferred
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
            instructions=instructions
        )
        datapath.send_msg(mod)
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]
        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=parser.OFPMatch(),
            instructions=instructions
        )
        datapath.send_msg(mod)
        print("Switch connected; table-miss rule installed.")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        print("Packet received: source =", src, "destination =", dst)

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)

            if ip_pkt:
              dscp = ip_pkt.tos >> 2
              print("DSCP value:", dscp)
              if dscp == CRITICAL_DSCP:
                queue_id = 1
              else:
                queue_id = 0

              actions = [
                parser.OFPActionSetQueue(queue_id),
                parser.OFPActionOutput(out_port)
              ]
              if dscp == CRITICAL_DSCP:
                flow_priority = CRITICAL_FLOW_PRIORITY
              elif dscp == ERROR_DSCP:
                flow_priority = ERROR_FLOW_PRIORITY
              else:
                flow_priority = DEFAULT_FLOW_PRIORITY

              match = parser.OFPMatch(
               in_port=in_port,
               eth_type=ether_types.ETH_TYPE_IP,
               eth_dst=dst,
               ip_dscp=dscp
              )
            else:
             flow_priority = DEFAULT_FLOW_PRIORITY
             match = parser.OFPMatch(
              in_port=in_port,
              eth_dst=dst
             )

            self.add_flow(
             datapath,
             flow_priority,
             match,
             actions
            )

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)
