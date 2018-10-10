#!/usr/bin/env python
import ConfigParser

#------------------------------
class NcsParser:
    def __init__(self, conf_file="./ncs.conf"):
        if conf_file == None:
            self.ncs_conf_file = "./ncs.conf"
        else:
            self.ncs_conf_file = conf_file
        
        self.handle = ConfigParser.ConfigParser()
        self.users = {}
        self.mountpoints = {}
        
    def parse(self):
        try:
            self.handle.read(self.ncs_conf_file)
            sections = self.handle.sections()
            for s in sections:
                if s == 'users':
                    users = dict(self.handle.items(s))
                    self.users["source_pwd"] = users["source_pwd"]

                    c_usr_pwd_pairs = users["client_usr"].split("|")
                    for i in c_usr_pwd_pairs:
                        u, p = i.split(":")
                        self.users[u] = p
                        
                if s == "mountpoints":
                    mountpoints = dict(self.handle.items(s))
                    self.mountpoints["mountpoints"] = mountpoints["mountpoint"].split("|")
        except:
            pass

    def get_users(self):
        return self.users
    
    def get_mountpoints(self):
        return self.mountpoints
