#!/usr/bin/env python
from struct import unpack
#import redis
from binascii import b2a_hex, a2b_hex
import json

#--------------------------------------
NO_CLASS   = 0
RTCM_CLASS = 1
READ_RESERVED =  1
READ_LENGTH   =  2
READ_MESSAGE  =  3
READ_CHECKSUM =  4

RTCM3_PREAMBLE = '\xD3'
RTCM3_MSG_1005 = '\x69'
RTCM3_MSG_1077 = '\xB1'
RTCM3_MSG_1087 = '\xBB'

UNINIT = 0
import struct
class RTCM3:
    def __init__(self):
        self.redis_handle = None
        self.source_mntp = None
        self.data = ""
        self.buf = ""
        self.state = 0 #
        self.type = 0
        self.byteIndex = 0
        self.checksumCounter = 0
        self.data_class = NO_CLASS
        self.rd_msg_len = 0
        self.rd_msg_len1 = 0
    
    def feed(self, data, redis_handle = None, source_mntp = None):
        self.redis_handle = redis_handle
        self.source_mntp = source_mntp
        self.data = data
        
    def init(self):
        self.state = UNINIT
        self.data_class = NO_CLASS
        self.buf = ""
        self.byteIndex = 0
        self.rd_msg_len = self.rd_msg_len1 = self.checksumCounter = 0
        
    def process(self):
        for buf in self.data:
            #print 'data state:', self.state
            if self.rd_msg_len > 1024 + 6 and self.state != UNINIT:
                self.init()
                continue
            
            if self.state != UNINIT and self.data_class == RTCM_CLASS:
                self.buf += buf
            
            if self.state == UNINIT:
                self.buf = ""
                if buf == RTCM3_PREAMBLE:
                    self.buf += buf
                    self.data_class = RTCM_CLASS
                    self.state = READ_RESERVED
                    
            elif self.state == READ_RESERVED:
                if buf != "\x00":
                    self.init()
                    continue
                tmp = unpack("B", buf)[0]
                self.rd_msg_len1 = tmp & 0b00000011
                self.state = READ_LENGTH
                
            elif self.state == READ_LENGTH:
                tmp = unpack("B", buf)[0]
                self.rd_msg_len = (self.rd_msg_len1 << 8) + tmp
                self.state = READ_MESSAGE
                
            elif self.state == READ_MESSAGE:
                if self.byteIndex == self.rd_msg_len - 1:
                    self.state = READ_CHECKSUM
                self.byteIndex += 1
                
            elif self.state == READ_CHECKSUM:
                self.checksumCounter += 1
                if self.checksumCounter == 3:
                    #print "rtcm data:", b2a_hex(self.buf)                    
                    self.redis_handle.publish(self.source_mntp, json.dumps(b2a_hex(self.buf)))
                    self.init()

if __name__ == "__main__":
    data = "d3005f4350005a33cc0200002405000200000000200000007d4529150d4800001e1d45fc4c8f8f4efe29fa30069f864405987618bd7e38bb62c526740d41ac1d790bf60a8c2910001412c20a82a0a7aa0a054190680f8501d9eed796da5325195d4017eb82"
    data = a2b_hex(data)
    
    rtcm_handle = RTCM3()
    rtcm_handle.feed(data)
    
    rtcm_handle.process()
    
    
    
    