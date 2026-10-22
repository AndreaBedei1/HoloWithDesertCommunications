"""Small applications: only local state, own communication handle and time."""
from __future__ import annotations
import random


class TrafficApplication:
    def __init__(self, communication, flows, seed=1):
        self.communication = communication
        self.flows = flows = [f for f in flows if f.generator=='python']
        self.next_send = [f.start for f in flows]
        self.emitted = [0 for _ in flows]
        self.random = [random.Random(seed * 100000 + int(f.source[-2:]) * 100 + i)
                       for i, f in enumerate(flows)]
        for i, flow in enumerate(flows):
            if flow.pattern == 'events':
                self.next_send[i] = flow.events[0] if flow.events else float('inf')

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
            self.emitted[i] += 1
            if flow.pattern == 'events':
                self.next_send[i] = flow.events[self.emitted[i]] if self.emitted[i] < len(flow.events) else float('inf')
                continue
            if flow.pattern == 'burst':
                cycle, offset = divmod(self.emitted[i], flow.burst_count)
                self.next_send[i] = flow.start + cycle * flow.burst_period_s + offset * flow.burst_interval_s
                continue
            interval = flow.interval
            if flow.final_interval is not None and flow.stop is not None:
                fraction = min(1, max(0, (now - flow.start) / (flow.stop - flow.start)))
                interval += fraction * (flow.final_interval - interval)
            self.next_send[i] = now + (self.random[i].expovariate(1 / interval)
                                       if flow.pattern == 'poisson' else interval)
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

    def snapshot(self, now):
        return {"role": "leader" if self.leader else "follower", "state": self.state,
                "last_heartbeat_s": self.last_receive,
                "heartbeat_age_s": None if self.last_receive is None else now - self.last_receive,
                "freshness_s": self.freshness}
