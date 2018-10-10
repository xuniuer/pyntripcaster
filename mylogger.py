#!/usr/bin/env python 

"""
    Log recorder (singleton pattern)
"""
import logging,logging.handlers
import os
import time

class Singleton(object):
    __instance = None
    
    def __new__(self):
        if self.__instance is None:
            self.__instance = object.__new__(self)
            self.__instance.init()
        return self.__instance 
           
    #subclass must override this function and use it to initialize instead of use __init__() 
    def init(self):
        pass

class MyLogger(Singleton):
    def init (self):
        if not os.path.exists("logs"):
            os.mkdir("logs")
        
        handler = logging.handlers.TimedRotatingFileHandler("./logs/ntripcaster.log", 'D', 1, backupCount = 30)
        handler.setFormatter(logging.Formatter('[%(asctime)s] - %(message)s'))
        logging.getLogger().addHandler(handler)
        self.logger = logging.getLogger("Jimmy Xu Ntripcaster service")
        self.logger.setLevel(logging.INFO)

    def info (self, contents):
        self.logger.info(contents)
    
    def error (self, contents):
        self.logger.error(contents)

def getLoggerInstance ():
    return MyLogger()
        

if __name__ == "__main__":
    getLoggerInstance().info("Hi@")