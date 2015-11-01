#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  db.py
#  
#  Copyright 2015 zeglor <zeglor@zeglor-desktop>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

from uuid import uuid4
from redis import StrictRedis
from secret import dbSettings

TTL = 120

class Db:
    _instance = None

    def __init__(self):
        # initialize connections
        pass

    def generateKey(self):
        pass

    def store(self, key, objSerial):
        pass

    def retrieve(self, key):
        pass

    def keyExists(self, key):
        pass

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class DbTest(Db):
    _instance = None
    storage = {}
    lists = {}

    def __init__(self):
        super().__init__()

    def generateKey(self):
        return str(uuid4())

    def store(self, key, objSerial):
        DbTest.storage[key] = objSerial

    def retrieve(self, key):
        return DbTest.storage.get(key)

    def lenList(self, name):
        try:
            return len(self.lists[name])
        except KeyError:
            return 0

    def listAppend(self, name, val):
        if self.lists.get(name) is None:
            self.lists[name] = []
        self.lists[name].append(val)

    def listPopLeft(self, name):
        if self.lists.get(name) is None or len(self.lists[name]) == 0:
            return None
        return self.lists[name].pop(0)

    def retrieveList(self, name):
        if self.lists.get(name) is None:
            return None
        return self.lists[name]

    def removeFromList(self, name, item):
        self.lists[name].remove(item)

    def keyExists(self, key):
        return key in DbTest.storage

class DbRedis(Db):
    def __init__(self):
        super().__init__()
        self.redis = StrictRedis(**dbSettings)

    def generateKey(self):
        return self.redis.incr('id')

    def store(self, key, objSerial):
        self.redis.setex(key, TTL, objSerial)

    def retrieve(self, key):
        return self.redis.get(key)

    def lenList(self, name):
        return self.redis.llen(name)

    def listAppend(self, name, val):
        self.redis.lpush(name,val)

    def listPopLeft(self, name):
        return self.redis.lpop(name)

    def retrieveList(self, name):
        return self.redis.lrange(name, 0, -1)

    def removeFromList(self, name, item):
        self.redis.lrem(name, item, 0)

    def keyExists(self, key):
        return self.redis.exists(key)



def main():
    db = DbRedis.instance()
    objSerial = "test"
    key = db.generateKey()
    print(key)
    db.store(key, objSerial)
    print(db.retrieve(key))


if __name__ == '__main__':
    main()
