import random
import threading
import time
import enum
import queue

SERVER = 0


class Message(object):
  def __init__(self, to, fr, type, info):
    self.to = to
    self.fr = fr
    self.type = type
    self.info = info
    self.names = {0: "SERVER", 1: "CLIENT"}
  def __str__(self):

    return "from: {fr}, to: {to}, type: {self.type}, info: " \
           "{self.info}".format(self=self, fr=self.names[self.fr], to=self.names[self.to])


class State(enum.Enum):
  INIT = 1
  OFFER = 2
  REQUESTING = 3
  ACKNOWLEDGED = 4
  END = 5


# Helper: Adds Message to queues of clients and server (equivalent to broadcast)
class Lan(object):

  def __init__(self, packet_queues):
    self.packet_queues = packet_queues

  def broadcast(self, message):
    print("broadcasting: ", message, "\n")
    for packet_queue in self.packet_queues:
      time.sleep(2)
      packet_queue.put(message)

  def __str__(self):
    s = ""
    for q in self.packet_queues:
      s += 'packet_queues: {queue}, '.format(queue=list(q.queue))

    return s

# A simplified server which keeps static list of available IPs and
# distributes them
class Server(object):

  def __init__(self, ips, packet_queue, lan):
    self.id = 0  # server id is 0
    self.ips = ips
    self.reserved = {}
    self.allocated = {}
    self.packet_queue = packet_queue
    self.lan = lan

  def start(self):
    threading.Thread(target=self.listen,
                     name='py-dhcp server thread').start()

  def __str__(self):
    return "id: {self.id}, lan: {self.lan}, ips: {self.ips}, reserved: " \
           "{self.reserved}, allocated: {self.allocated}".format(self=self)

  def listen(self):

    while True:
      time.sleep(5)
      try:
        packet = self.packet_queue.get(block=True, timeout=3)
      except:
        continue

      # is it for me?
      if packet.to != SERVER:
        continue
      elif packet.type == "DISCOVER":
        # if no ips present to offer, return an offer with empty IP.
        try:
          ip = self.ips.pop()
          self.lan.broadcast(Message(packet.fr, SERVER, "OFFER", ip))
          self.reserved[packet.fr] = ip
        except IndexError:
          self.lan.broadcast(Message(packet.fr, SERVER, "OFFER", ""))
      elif packet.type == "REQUEST":
        # remove from reserved and put in allocated
        ip = self.reserved[packet.fr]
        self.allocated[packet.fr] = ip
        self.reserved.pop(packet.fr, None)
        # broadcast acknowledgement
        self.lan.broadcast(Message(packet.fr, SERVER, "ACKNOWLEDGEMENT", ip))
      else:
        continue


# Simplified goal of client: get an IP by requesting the dhcp server and exit.
# if request rejected, try again
class Client(object):

  def __init__(self, id, lan, packet_queue):
    self.id = id
    self.lan = lan
    self.packet_queue = packet_queue
    self.ip = None
    self.state = State.INIT

  def __str__(self):
    return "id: {self.id}, lan: {self.lan}, ip: {self.ip}, state: " \
           "{self.state}".format(self=self)

  def discover(self):
    # tries only once (assuming it succeeds in one try)
    discover_message = Message(SERVER, self.id, "DISCOVER", "")
    # for simulation purpose
    time.sleep(random.randint(1, 3))

    # broadcast
    self.lan.broadcast(discover_message)

  def listen(self):
    while True:  # simply try checking the queue after 2 seconds
      time.sleep(5)
      if self.state == State.ACKNOWLEDGED:
        if self.ip is None:
          print("Error")  # debug
        self.state = State.END
        print("Assigned IP: ", self.id, self.ip)
        break
      # read packet from queue
      try:
        packet = self.packet_queue.get(block=True, timeout=3)
      except:
        continue

      if packet.fr != 0 or packet.to != self.id:
        # discard
        continue

      if packet.type == "OFFER":
        # print(self, ": offer rejected, ip = ", packet.info, "\n")
        if not packet.info:
          # request rejected, try again
          self.discover()
          continue
        self.state = State.OFFER
        request_message = Message(SERVER, self.id, "REQUEST", packet.info)
        self.lan.broadcast(request_message)
        self.state = State.REQUESTING

      if packet.type == "ACKNOWLEDGEMENT":
        self.ip = packet.info
        self.state = State.ACKNOWLEDGED

  def start(self):
    threading.Thread(target=self.listen, name='py-dhcp listen thread').start()
    self.discover()


def main():
  num_clients = 1
  clients = []
  queues = []
  for id in range(num_clients+1):
    queues.append(queue.Queue())

  lan = Lan(queues)

  for id in range(1, num_clients + 1):
    clients.append(Client(id, lan, queues[id]))

  ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
  server = Server(ips, queues[SERVER], lan)

  server.start()
  for i in range(1, num_clients + 1):
    clients[i - 1].start()

if __name__ == "__main__":
  main()
