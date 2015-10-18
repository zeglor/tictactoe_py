from gevent import monkey
from gevent.server import StreamServer
from gevent.pool import Pool
monkey.patch_all()

from time import sleep

def handle(socket, address):
	print("New connection!")
	counter = 1
	while(True):
		socket.send("echo-{}".format(counter).encode('utf8'))
		sleep(1)
		counter += 1
	#check if there are waiting players
	#if there are, create new game instance and connect them to each other
	#if not, send this client to waiting queue

pool = Pool(1000)
server = StreamServer(('127.0.0.1', 1234), handle, spawn=pool)
server.serve_forever()
