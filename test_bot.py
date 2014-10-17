#encoding=utf-8


import ircclient, bot_funcs, sys, traceback, imp


class channel_service(ircclient.irc_channel):

	def set_synchronized(self):
		ircclient.irc_channel.set_synchronized(self)
		self.action("är nu online!")

	def handle_generic(self, prefix, message):
		try:
			return bot_funcs.handle_generic(self, prefix, message)
		except:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			self.privmsg("Gah! Fick internt fel nu >.<   Djävla %s" % exc_type.__name__)
			traceback.print_exc()
		

	def handle_privmsg(self, prefix, message):
		return self.handle_generic(prefix, message)

	def handle_notice(self, prefix, message):
		return self.handle_generic(prefix, message)

	def handle_action(self, prefix, message):
		return self.handle_generic(prefix, message)

class bot(ircclient.irc_client):
	def __init__(self, *args, **kw_args):		
		kw_args['channel_manager'] = channel_service	#Use our own channel manager
		ircclient.irc_client.__init__(self, *args, **kw_args)

	def sigint_handler(self, signal, frame):
		for channel in self.channels.values():
			channel.action("måste dra, fick en SIGINT!")
		self.quit()


	#We could overload handle_privmsg and similar here if we want


b = bot(nick="Leddie", host="ledalert.org", irc_server="irc.freenode.net",full_name="LED Alert Bot", verbose=True, join_channels=["#labottest", "#ledalert"])

def reload_funcs():
	try:
		imp.reload(bot_funcs)
		for channel in b.channels.values():
			channel.action("laddade om funktionsbiblioteket och blev eventuellt mer awesome!")

	except:
		exc_type, exc_value, exc_traceback = sys.exc_info()
		for channel in b.channels.values():
			channel.privmsg("Gah! Fick internt fel vid omladdning >.<   Djävla %s" % exc_type.__name__)
		traceback.print_exc()

b.debug=True
import signal
signal.signal(signal.SIGINT, b.sigint_handler)
b.connect()
b.start()
#b.join()	#Wait for thread to finish!
