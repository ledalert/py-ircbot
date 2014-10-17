#encoding=utf-8

import re, tempfile, subprocess, os

url_regexp = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

#lookup_url kollar nu headers och även charset för att tolka titel korrekt
#TODO: kolla metataggar för mime-typ


def scall(*args):
	return subprocess.call(args)

class tempdir:
	def __init__(self):
		self.dir = None

	def __enter__(self):
		self.dir = tempfile.mkdtemp()
		return self.dir
	
	def __exit__(self ,type, value, traceback):
		scall('rm', '-rf', self.dir)

def lookup_url(client, url):
	with tempdir() as td:
		headers = os.path.join(td, 'headers')
		data = os.path.join(td, 'data')
		os.mkfifo(data)
		proc = subprocess.Popen(('curl', '-L', '-D', headers, '-o', data, url))
		with open(data, 'rb') as fifo:
			chunk = fifo.read(64*1024)	#max 64k

		proc.wait()
		
		content_type = "(Okänd innehållstyp)"
		charset=None
		with open(headers, 'rb') as hdata:
			for line in hdata.read().split(b'\r\n'):
				if line[:13].lower() == b'content-type:':
					content_type = line[13:]
					if b';' in content_type:
						content_type, charset = content_type.split(b';',1)
						charset = charset.split(b'=', 1)[1].strip(b'\r\n\t ')
						

					content_type = str(content_type.strip(b'\r\n\t '), 'latin1')

		
		#chunk has first 64k of data

		title="(Okänd titel)"

		lchunk = chunk.lower()
		pos1 = lchunk.find(b'<title>')
		if pos1 != -1:
			pos2 = lchunk.find(b'</title>', pos1)
			title = chunk[pos1+7:pos2].strip(b'\r\n\t ')

		#b' charset="UTF-8" /'
		print ("charset in header", charset)

		start = None
		while 1:
			pos1 = lchunk.find(b'<meta', start)
			if pos1 == -1:
				break
			pos2 = lchunk.find(b'>', pos1)
			meta_tag = lchunk[pos1+5:pos2]
			if b'charset' in meta_tag:
				meta_tag = meta_tag.split(b'charset', 1)[1]
				if b'"' in meta_tag:
					try:
						charset = meta_tag.split(b'"')[1].strip(b'\r\n\t ')
					except:
						pass
				elif b"'" in meta_tag:
					try:
						charset = meta_tag.split(b"'")[1].strip(b'\r\n\t ')
					except:
						pass


			start = pos2

		print ("charset possibly in meta", charset)


		if charset != None:
			#Parse charset as latin1
			charset = str(charset, 'latin1')

		try:
			#We will fallback on utf-8
			title = str(title, charset or 'utf-8')
		except:
			pass

		return content_type.strip(), charset or '(Okänd teckenkodning)', title


#curl "http://www.swedbank.se" -D - -s

def handle_generic(channel, prefix, message):
	client = channel.client
	msg=client.decode(message)

	urls = re.findall(url_regexp, msg)
	print("Raw message: ", repr(message))	
	if urls:
		for url in urls:
			content_type, charset, title = lookup_url(client, url)
			channel.privmsg("\x033\x02%s\x02 %s \x036:: \x0f%s" % (content_type, charset, title))

	return True