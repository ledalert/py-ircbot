#encoding=utf-8

import sys, threading, queue, socket

#TODO: Handle various errors, like nick taken etc

def e_print(*args):
	for arg in args:
		sys.stderr.write(arg)
	sys.stderr.write('\n')
	sys.stderr.flush()

class IRC_PROTOCOL:
	RPL_NAMREPLY = 353
	RPL_ENDOFNAMES = 366

class irc_message:
	def __init__(self, prefix, cmd, message):
		self.prefix = prefix
		self.cmd = cmd
		self.message = message

	def __str__(self):
		return '<irc_message cmd=%s prefix=%s message=%s>' % (self.cmd, self.prefix, self.message)


class irc_channel:
	def __init__(self, client, name):
		self.name = name
		self.client = client
		self.names=set()
		self.synchronized=False

	def add_names(self, names):
		self.names |= set(names)

	def set_synchronized(self):
		self.synchronized=True
		if self.client.verbose:
			e_print("Channel %s synchronized!" % self.name)

	def handle_privmsg(self, prefix, message):
		return False

	def handle_notice(self, prefix, message):
		return False

	def handle_action(self, prefix, message):
		return False

	def privmsg(self, message):
		self.client.send_cmd('PRIVMSG', self.name, b':'+self.client.encode(message))

	def notice(self, message):
		self.client.send_cmd('NOTICE', self.name, b':'+self.client.encode(message))

	def action(self, message):
		self.privmsg(b'\x01ACTION ' + self.client.encode(message) + b'\x01')


class irc_client(threading.Thread):

	IDLE = 1
	CONNECTING = 5
	REGISTERING = 10
	JOINING = 15
	JOINED = 20


	def encode(self, data):
		if type(data) == bytes:
			return data
		if type(data) == str:
			return bytes(data, self.encoding)
		return None

	def decode(self, data):
		if type(data) == str:
			return data
		if type(data) == bytes:
			return str(data, self.encoding)
		return None

	def __init__(self, nick=None, user=None, host=None, full_name=None, server=None, irc_server=None, irc_port=6667, verbose=False, encoding="utf-8", debug=False, join_channels=None, channel_manager=irc_channel):
		threading.Thread.__init__(self)
		self.nick = nick
		self.user = user
		self.host = host
		self.channel_manager = channel_manager
		self.join_channels = join_channels
		self.channels = dict()
		self.full_name = full_name or "Unnamed Client"
		self.registered_nick = None

		self.message_queue_incoming = queue.Queue()
		self.message_queue_outgoing = queue.Queue()

		if not self.user:
			if self.nick:
				self.user = self.nick.lower()

		self.server = server or '*'
		self.verbose = verbose
		self.debug = debug
		self.irc_server = irc_server
		self.irc_port = irc_port

		self.recv_thread=None
		self.send_thread=None
		self.message_handler_thread = None
		self.running = False
		self.socket= None
		self.encoding = encoding
		self.bufsize = 4096	#4k should be enough
		self.handlers = [self.default_handler]
		self.state = irc_client.IDLE

	def connect(self):
		self.verify_connect()

		if self.verbose:			
			e_print("Connecting to server %s:%s\n" % (self.irc_server, self.irc_port))

		self.state = irc_client.CONNECTING
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((self.irc_server, self.irc_port))

		if self.verbose:			
			e_print("Starting threads")

		self.recv_thread = threading.Thread(target=self._recv_thread)			
		self.send_thread = threading.Thread(target=self._send_thread)
		self.message_handler_thread = threading.Thread(target=self._message_handler_thread)
		self.running = True
		self.recv_thread.start()
		self.send_thread.start()
		self.message_handler_thread.start()

		if self.verbose:			
			e_print("Sending NICK and USER")

		self.state = irc_client.REGISTERING
		self.send_cmd('NICK', self.nick)
		self.send_cmd('USER', self.user, self.host, self.server, ':'+self.full_name)


	def send_cmd(self, *args):
		self.message_queue_outgoing.put(b' '.join([self.encode(arg) for arg in args]) + b'\r\n')

	def verify_connect(self):
		if not (self.irc_server and self.irc_port):
			raise Exception("Can't connect without irc_server and irc_port!")

		if not (self.user and self.nick and self.host and self.server):
			raise Exception("Can't connect without user, nick, host and server argument for NICK and USER!")

		if not (self.full_name):
			raise Exception("Can't connect without full_name argument for USER!")

		if (self.send_thread or self.recv_thread):
			raise Exception("Already has threads running, coder needs to implement nice shutdown, even if error!")

	def _recv_thread(self):
		if self.verbose:
			e_print("Recieving thread started")

		buf = b''
		while self.running:
			data = self.socket.recv(self.bufsize)
			if not data:
				break

			buf += data

			while b'\r\n' in buf:
				message, buf = buf.split(b'\r\n', 1)
				self._decode_message(message)


		self.running = False
		if self.verbose:
			e_print("Recieving thread terminated")

	def _decode_message(self, message):
		if self.debug:
			e_print ("raw message: %s" % message)

		if message[0:1] == b':':
			prefix, message = message[1:].split(b' ', 1)
			cmd, message = message.split(b' ', 1)
			self.message_queue_incoming.put(irc_message(prefix, cmd, message))

		else:
			cmd, message = message.split(b' ', 1)
			self.message_queue_incoming.put(irc_message(None, cmd, message))
			
			#e_print("No prefix - ignoring message: %s" % message)



	def _message_handler_thread(self):
		if self.verbose:
			e_print("Message handler thread started")

		while self.running:
			message = self.message_queue_incoming.get()
			
			for handler in self.handlers:
				if handler(message):
					break

			else:
				e_print("Unhandled message: %s" % message)


		self.running = False
		if self.verbose:			
			e_print("Message handler thread terminated")


	def handle_privmsg(self, prefix, msg):
		return False

	def handle_notice(self, prefix, msg):
		return False

	def handle_action(self, prefix, msg):
		return False
		
	def default_handler(self, message):

		if message.prefix == None:

			#PING :kornbluth.freenode.net

			if message.cmd.lower() == b'ping':
				if self.verbose:
					e_print("PING %s" % message.message)
				self.send_cmd('PONG', message.message)
				return True

		else:

			if message.cmd.lower() == b'mode':
				if self.state == irc_client.REGISTERING:
					#cmd: b'MODE', from: b'Leddie' args: b'Leddie :+i'
					self.registered_nick = message.prefix
					if self.verbose:
						if self.join_channels:
							e_print("Joining channels: %s" % self.join_channels)
						else:
							e_print("No channels specified")


					if self.join_channels:
						self.state = irc_client.JOINING
						self.send_cmd('JOIN', ','.join(self.join_channels))
					else:
						self.state = irc_client.JOINED

					return True


			if message.cmd.lower() == b'join':
				if self.state == irc_client.JOINING:
					self.channels[message.message] = self.channel_manager(self, message.message)
					return True



			if message.cmd.lower() == b'privmsg':
			#prefix=b'Devilholk!~devilholk@luder.nu' message=b'#ledalert :test'
				dest, msg = message.message.split(b' ', 1)

				#:\x01ACTION g\xc3\xb6r saker\x01

				if msg[:9].lower() == b':\x01action ':
					if dest in self.channels:
						return self.channels[dest].handle_action(message.prefix, msg[9:-1])
					if dest == self.registered_nick:
						return self.handle_action(message.prefix, msg[9:-1])
				else:
					if dest in self.channels:
						return self.channels[dest].handle_privmsg(message.prefix, msg[1:])
					if dest == self.registered_nick:
						return self.handle_privmsg(message.prefix, msg[1:])


			if message.cmd.lower() == b'notice':
			#prefix=b'Devilholk!~devilholk@luder.nu' message=b'#ledalert :test'
				dest, msg = message.message.split(b' ', 1)
				if dest in self.channels:
					return self.channels[dest].handle_notice(message.prefix, msg[1:])
				if dest == self.registered_nick:
					return self.handle_notice(message.prefix, msg[1:])


			if message.cmd.isdigit():			
				cmdnum = int(message.cmd)
				
				# Leddie = #ledalert :Leddie freak Nekros_ Devilholk gurgalof TimGremalm
				#= is for public channel

				if cmdnum == IRC_PROTOCOL.RPL_NAMREPLY:
					args = message.message.split(b' ')
					myself = args.pop(0)
					if args[0] in b'=*@':
						publicity = args.pop(0)
					channel = args.pop(0)
					args[0] = args[0][1:]	#remove :

					self.channels[channel].add_names(args)
					return True

				#Leddie #ledalert :End of /NAMES list.
				if cmdnum == IRC_PROTOCOL.RPL_ENDOFNAMES:
					args = message.message.split(b' ')
					myself = args.pop(0)
					channel = args.pop(0)

					self.channels[channel].set_synchronized()
					return True
					




		return False

	def _send_thread(self):
		if self.verbose:
			e_print("Sending thread started")

		while self.running:
			message = self.message_queue_outgoing.get()

			if message == None:	#Sentinel for thread termination
				break

			#Here we can add message object handling as well later, now we just handle raw messages
			if type(message) == bytes:
				if self.debug:
					e_print("sending: %s" % message)
				self.socket.send(message)
			else:
				e_print("Warning! Unknown message in outgoing queue: %s" % message)


		self.running = False
		if self.verbose:			
			e_print("Sending thread terminated")

	def run(self):
		self.recv_thread.join()
		self.send_thread.join()
		self.message_handler_thread.join()

	def stop(self):
		self.running = False

	def quit(self, message=None):
		if message:
			self.send_cmd('QUIT', ':'+message)
		else:
			self.send_cmd('QUIT')
		self.message_queue_outgoing.put(None) #Add sentinel to outgoing thread

	def sigint_handler(self, signal, frame):
		self.quit("User interface recieved SIGINT")