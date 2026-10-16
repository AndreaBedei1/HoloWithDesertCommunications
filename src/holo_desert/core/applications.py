"""Small applications: only local state, own communication handle and time."""
from __future__ import annotations


class TrafficApplication:
    def __init__(self, communication, flows):
        self.communication = communication
        self.flows = flows
        self.next_send = [f.start for f in flows]

    def update(self, now, own_pose, received):
        for delivery in received:
            if delivery.message.message_type == "request":
                self.communication.send(delivery.message.source, b"ack:" + delivery.message.payload,
                                        message_type="reply", ttl=delivery.message.ttl)
        for i, flow in enumerate(self.flows):
            if now + 1e-9 < self.next_send[i] or (flow.stop is not None and now >= flow.stop):
                continue
            self.communication.send(flow.destination, b"x" * flow.payload_bytes,
                                    message_type="request" if flow.reply else flow.message_type, ttl=flow.ttl)
            interval = flow.interval
            if flow.final_interval is not None and flow.stop is not None:
                fraction = min(1, max(0, (now - flow.start) / (flow.stop - flow.start)))
                interval += fraction * (flow.final_interval - interval)
            self.next_send[i] = now + interval
        return None


class HeartbeatCoordinator:
    """Follower proceeds only with a recently received heartbeat.

    No peer pose or clock is read. The freshness check uses the actual network
    arrival time. Outage and recovery are produced by PHY power in DESERT.
    """
    def __init__(self, communication, peer, target, leader=False, freshness=3.0):
        self.communication = communication
        self.peer = peer
        self.target = target
        self.leader = leader
        self.freshness = freshness
        self.last_receive = None
        self.next_send = 1.0
        self.state = "WAITING"
        self.hold = None

    def update(self, now, own_pose, received):
        if self.leader:
            if now >= self.next_send:
                self.communication.send(self.peer, b"clear", message_type="heartbeat", ttl=3)
                self.next_send = now + 1
            self.state = "ANNOUNCING"
            return None
        for delivery in received:
            if delivery.message.source == self.peer and delivery.message.message_type == "heartbeat":
                self.last_receive = delivery.network_time
        fresh = self.last_receive is not None and now - self.last_receive <= self.freshness
        state = "PROCEED" if fresh else "HOLD"
        if state == "HOLD" and self.state != "HOLD":
            self.hold = (own_pose.x, own_pose.y, own_pose.z, 0, 0, own_pose.yaw)
        self.state = state
        return (*self.target, 0, 0, own_pose.yaw) if fresh else self.hold
