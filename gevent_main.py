#!/usr/bin/env python
#coding:utf-8
from gevent import monkey; monkey.patch_all()

import gevent
from gevent import socket
import redis
from gevent.server import StreamServer
import base64
import time
import json
from binascii import b2a_hex, a2b_hex

from rtcm3 import RTCM3
from mylogger import getLoggerInstance
from ncsconf import NcsParser
from traceback import print_exc
import time

#------------------------------
g_users = {}        # {'source_pwd': 'sesam01', 'user2': 'password2', 'user': 'password'}
g_mountpoints = {}  # {'mountpoints': ['AUTO', 'TEST', 'XUYJ']}

pool = redis.ConnectionPool(host="127.0.0.1", port=6379, db=0)
redis_handle = redis.StrictRedis(connection_pool=pool)
g_source_mntps = {}
#------------------------------
def check_mountpoint(mp):
    global g_mountpoints
    
    try:
        if mp in g_mountpoints["mountpoints"]:
            return True
        else:
            return False
    except:
        return False
    
#------------------------------
def check_user(usr, pwd):
    '''
    If user == "source_pwd", to check source password
    else to check ntrip client user/pwd validation
    '''
    global g_users
    
    try:
        p = g_users[usr]
        if p == pwd:
            return True
        else:
            return False
    except:
        return False            

#------------------------------
def report_source_table():
    tpl = """SOURCETABLE 200 OK\r\n
Server: JIMMYXU NTRIP Caster 0.1\r\n
Content-Type: text/plain\r\n
Content-Length: %d\r\n
Date: %s\r\n
\r\n
%s\r\n
ENDSOURCETABLE\r\n"""
    source_table_contents = open("sourcetable.txt", "r").read()
    source_table_len = len(source_table_contents)
    date_string = time.asctime()
    
    return tpl % (source_table_len, date_string, source_table_contents)


#--------------------------------------
# refer to: https://stackoverflow.com/questions/12248132/how-to-change-tcp-keepalive-timer-using-python-script
def set_keepalive_linux(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    """Set TCP keepalive on an open socket.

    It activates after 1 second (after_idle_sec) of idleness,
    then sends a keepalive ping once every 3 seconds (interval_sec),
    and closes the connection after 5 failed ping (max_fails), or 15 seconds
    """
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)

# Ntrip client request
"""
GET /TEST2 HTTP/1.1
User-Agent: NTRIP sNTRIP/1.10.0
Accept: */*
Authorization: Basic Z3Vlc3Q6dGVzdA==

"""
#--------------------------------------
# Ntrip source request
"""
SOURCE test TEST2
Source-Agent: NTRIP RTKLIB/2.4.3 demo5
STR:

"""

#--------------------------------------
def NtripCasterServer(sock, address):

    global redis_handle
    global g_source_mntps

    is_ntrip_source = False
    is_ntrip_client = False
    source_mntp = ""
    client_mntp = ""
    
    rtcm_handle = RTCM3()
    
    set_keepalive_linux(sock)
    
    conn_id = "{%s - %d}" % (address[0], address[1])
    
    data = "dummy"
    while len(data):
        
        try:
            x = sock.getpeername()
        except:
            if is_ntrip_client:
                getLoggerInstance().info("ntrip client [%s] is closed." % conn_id)
                
            if is_ntrip_source:
                getLoggerInstance().info("ntrip source [%s] is closed." % conn_id)

            sock.close()          
            return
        
        try:
            data = sock.recv(1024)
        except:
            getLoggerInstance().info("socket recv exception!")
            sock.close()
            return 
        
        if data.startswith("SOURCE"):   # ntrip source
            
            lines = data.splitlines()

            #print "---------------------------"
            #print lines
            #print "---------------------------"
            
            for line in lines:
                if line.startswith("SOURCE"):
                    source_pwd, source_mntp = line.split()[1:]
                    if source_mntp[0] != '/': 
                        source_mntp = '/' + source_mntp
                    
                    getLoggerInstance().info("source: %s - %s" % (source_pwd, source_mntp))
                    if not check_user("source_pwd", source_pwd):
                        getLoggerInstance().info("Ntrip source password is invalid - %s" % source_pwd)
                        try:
                            sock.sendall("HTTP/1.0 401 Unauthorized\r\n")
                            sock.close()
                        except:
                            getLoggerInstance().info("Ntrip source -auth- is offline")
                            
                        return
                    
                    elif not check_mountpoint(source_mntp):
                        getLoggerInstance().info("Ntrip source is trying to use an undefined mountpoint - %s" % source_mntp)
                        
                        try:
                            sock.sendall("ERROR - Bad Mountpoint\r\n")
                            sock.close()
                        except:
                            getLoggerInstance().info("Ntrip source -mntp- is offline")
                            
                        return
                    
                    else:
                        is_ntrip_source = True
                        if source_mntp not in g_source_mntps.keys():
                            g_source_mntps[source_mntp] = address
                            getLoggerInstance().info("Ntrip source for [%s] is ready! from connected from (%s:%s)" % (source_mntp, address[0], str(address[1])))
                            sock.sendall("ICY 200 OK\r\n")
                            break
                        
                        else:
                            addr = g_source_mntps[source_mntp]
                            if addr <> address: # same connection
                                getLoggerInstance().info("[%s] has been used by another Ntrip source!" % source_mntp)
                                try:
                                    sock.sendall("ERROR - Bad Mountpoint\r\n")
                                    sock.close()
                                except:
                                    pass
                                return
                            else:
                                getLoggerInstance().info("[%s] - same ntrip source connection" % source_mntp)
                                break
                                
                        
        elif data.startswith("GET"):      # ntrip client
            lines = data.splitlines()
            
            #print "---------------------------"
            #print lines
            #print "---------------------------"
            
            for line in lines:
                if line.startswith("GET"):
                    client_mntp = line.split()[1]
                    getLoggerInstance().info('Ntrip client is trying to use mountpoint:%s' % client_mntp)
                    if client_mntp == "/": # request source table
                    
                        source_table = report_source_table()
                        getLoggerInstance().info("Ntrip client -sourcetable- returned")
                        sock.sendall(source_table)
                        continue
                    
                    else:
                        if not check_mountpoint(client_mntp): # wrong mountpoint
                            getLoggerInstance().info("Ntrip client is trying to use undefined mountpoint - %s" % (client_mntp))
                            try:
                                sock.sendall("ERROR - Bad Mountpoint\r\n")
                                sock.close()
                            except:
                                pass
                            return
                        
                elif line.startswith("Authorization"):
                    usr_pwd = line.split()[-1]
                    usr_pwd = base64.b64decode(usr_pwd)
                    cusr,cpwd = usr_pwd.split(":")
                    
                    if not check_user(cusr, cpwd):
                        getLoggerInstance().info("Ntrip client authentication error - %s:%s" % (cusr, cpwd))
                        try:
                            sock.sendall("ERROR - Bad Password\r\n")
                            sock.close()
                        except:
                            pass
                        return
                    
                    else:
                        getLoggerInstance().info("Ntrip client connected from (%s:%s)" % (address[0], str(address[1])))
                        sock.sendall("ICY 200 OK\r\n")
                        is_ntrip_client = True
                        
                        redis_pubsub = redis_handle.pubsub()
                        redis_pubsub.subscribe(client_mntp)
                        
                        stamp = time.time() + 20
                        while time.time() < stamp:
                            msg = redis_pubsub.get_message(True)
                            if msg and msg['type'] == 'message':
                                #print msg['data']
                                rdata = a2b_hex(json.loads(msg['data']))
                                
                                if rdata == "exit":
                                    getLoggerInstance().info("Ntrip client recv EXIT command from subscribed source mountpoint(%s)" % client_mntp)
                                    break
                                else:
                                    try:
                                        sock.sendall(rdata)
                                    except:
                                        pass
                                    
                                stamp = time.time() + 20
                            time.sleep(0.002)
                            
                        redis_pubsub.close()                        
                        sock.close()
                        break                                
                        
        else:
            # RTCM data expected
            if data:
                rtcm_handle.feed(data, redis_handle, source_mntp)
                rtcm_handle.process()
                
            else:
                if is_ntrip_source and source_mntp in g_source_mntps.keys():
                    getLoggerInstance().info("Ntrip source no data receivced.")
                    redis_handle.publish(source_mntp, json.dumps(b2a_hex("exit")))
                    del g_source_mntps[source_mntp]
                    
                    sock.close()
                    return
                    

#--------------------------------------
if __name__ == "__main__":
    import sys
    ncs_parser = NcsParser()
    ncs_parser.parse()
    
    g_mountpoints = ncs_parser.get_mountpoints()
    g_users = ncs_parser.get_users()
    print ("-------------------------------------------")
    print "[users      ]:", g_users
    print "[mountpoints]:", g_mountpoints
    
    server_port = 8000  
    server_addr = ('0.0.0.0', server_port)
    
    print ("Ntrip caster serve at %d" % server_port)
    print ("-------------------------------------------")

    # to make the server use SSL, pass certfile and keyfile arguments to the constructor
    ncs = StreamServer(server_addr, NtripCasterServer)

    try:
        ncs.serve_forever()
    except KeyboardInterrupt:
        getLoggerInstance().info("NtripCaster is terminated!\n\n\n")
        getLoggerInstance().info("--------------------------")

        