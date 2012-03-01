# -*- coding: utf-8 -*-
    
import asyncore
from asynchat import async_chat
import socket
import config
from threading import Thread
import manager
import logging

def start(state):
    global listener, thread
    listener = Listener()
    thread = Thread(target=asyncore.loop)
    thread.daemon = 1
    thread.start()
    return listener

def reconnect():
    global listener
    logging.info("Recreating listener...")
    old = listener
    listener = Listener()
    old.close_when_done()
    
class Listener(async_chat):
    READING_DATA = 0
    READING_META = 1
    READING_METASIZE = 2
    READING_HEADERS = 3
    def __init__(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((config.icecast_host, config.icecast_port))
        async_chat.__init__(self, sock=sock)
        logging.info("Started listener")
        self.ibuffer = []
        self.obuffer = 'GET {mount} HTTP/1.1\r\nHOST: {host}\r\nUser-Agent: Hanyuu-sama\r\nIcy-MetaData: 1\r\n\r\n'.format(mount=config.icecast_mount, host=config.icecast_host)
        self.push(self.obuffer)
        self.set_terminator('\r\n\r\n')
        self.status = self.READING_HEADERS
        
    def shutdown(self):
        self.close_when_done()
        thread.join()
        return None
    
    def collect_incoming_data(self, data):
        self.ibuffer.append(data)

    def parse_headers(self, headers):
        self.headers = {}
        headers = headers.split('\r\n')
        self.headers["status"] = tuple(headers[0].split(" "))
        for header in headers[1:]:
            if (not header):
                break
            splitted = header.split(":")
            self.headers[splitted[0].strip()] = splitted[1].strip()
            
    def found_terminator(self):
        if (self.status == self.READING_DATA):
            # We read the current chunk of data
            # Flush our data, we don't need it right now
            self.ibuffer = []
            # Terminator to 1 to read the size of metadata incoming
            self.set_terminator(1)
            self.status = self.READING_METASIZE
            
        elif (self.status == self.READING_HEADERS):
            logging.debug("Reading headers")
            self.reading_headers = False
            self.parse_headers("".join(self.ibuffer))
            self.ibuffer = []
            
            # Get the meta int value
            try:
                self.metaint = int(self.headers["icy-metaint"])
            except (KeyError):
                # Incorrect header, kill ourself after a small timeout
                sleep(5)
                reconnect()
            # set terminator to that int
            self.set_terminator(self.metaint)
            # Icecast always sends data after the headers, so go to that mode
            self.status = self.READING_DATA
            
        elif (self.status == self.READING_METASIZE):
            
            # Do an ord() and then times 16 to get the meta length in bytes
            self.metalen = ord(self.ibuffer[0]) * 16
            # Flush the byte afte reading it
            self.ibuffer = []
            if (self.metalen == 0):
                self.set_terminator(self.metaint)
                self.status = self.READING_DATA
            else:
                self.set_terminator(self.metalen)
                self.status = self.READING_META
            
        elif (self.status == self.READING_META):
            # finally reading some metadata
            incoming_string = "".join(self.ibuffer)
            incoming_string = incoming_string.rstrip("\x00")
            metadata = ""
            
            for part in incoming_string.split("';"):
                try:
                    if (part.strip().split("='")[0].lower() == "streamtitle"):
                        metadata = "='".join(part.split("='")[1:])
                except (IndexError):
                    pass
            new_song = manager.Song(meta=metadata)

            if (manager.np != new_song):
                manager.np.change(new_song)
            
            # flush buffer
            self.ibuffer = []
            # Change to metaint again for reading data
            self.set_terminator(self.metaint)
            # go back to reading data
            self.status = self.READING_DATA
