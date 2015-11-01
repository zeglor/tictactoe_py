#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  game.py
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

from gevent import monkey, sleep

monkey.patch_all()
from enum import Enum
from random import choice
from datetime import datetime
from db import DbRedis as Db
import json

CONNECTION_TIMEOUT = 10  # max time since last request until the player is considered disconnected
GAME_WAITING_QUEUE = "game_waiting_queue"


class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return {"__enum__": str(obj)}
        return json.JSONEncoder.default(self, obj)


def as_enum(d):
    if "__enum__" in d:
        name, member = d["__enum__"].split(".")
        return getattr(globals()[name], member)
    return d


class GameState(Enum):
    idle = 1
    searchingPlayers = 2
    active = 3
    playerLeft = 4
    finished = 5


class Game:
    @staticmethod
    def findNew(player):
        db = Db.instance()
        game = None
        # check if there are any games waiting for second player
        if db.lenList(GAME_WAITING_QUEUE) > 0:
            # if there are, remove one from queue
            gameKey = db.listPopLeft(GAME_WAITING_QUEUE)
            game = Game(gameKey)
        else:
            # if not, create new game and append it to waiting list
            game = Game()
            game.state = GameState.searchingPlayers
            db.listAppend(GAME_WAITING_QUEUE, game.key)
        game.addPlayer(player)
        game.update()
        return game

    def __init__(self, key=None):
        self.key = key
        self.players = []  # player[0] is 'o', player[1] is 'x'
        self.activePlayer = None  # whose turn is now?
        self.grid = ['' for _ in range(9)]  # 3x3 game grid
        # This variable is needed to keep in sync with both players. It is
        # incremented each time game state is updated (e.g. player makes a move).
        # Each player stores his value of stateFrame, so if player's copy is
        # less than game's, his game state is considered outdated
        self.stateFrame = 0
        self.winner = None
        self.state = GameState.idle

        db = Db.instance()
        if self.key is None or db.retrieve(self.key) is None:
            self.key = db.generateKey()
        else:
            self.deserialize(db.retrieve(self.key))
            self.checkIfPlayersActive()

    def serialize(self):
        obj = {}
        obj["key"] = self.key
        obj["players"] = [player.key for player in self.players]
        obj["activePlayer"] = self.activePlayer.key if self.activePlayer is not None else None
        obj["grid"] = self.grid
        obj["stateFrame"] = self.stateFrame
        obj["winner"] = self.winner.key if self.winner is not None else None
        obj["state"] = self.state
        return json.dumps(obj, cls=EnumEncoder).encode('UTF8')

    def deserialize(self, objStr):
        obj = json.loads(objStr.decode('UTF8'), object_hook=as_enum)
        self.key = obj["key"]
        playerKeys = obj["players"]
        try:
            playerKeys.remove(None)
        except ValueError:
            pass
        self.players = [Player(key, self) for key in playerKeys]
        self.activePlayer = Player(obj["activePlayer"], self) if obj["activePlayer"] is not None else None
        self.grid = obj["grid"]
        self.stateFrame = obj["stateFrame"]
        self.winner = Player(obj["winner"], self)
        self.state = obj["state"]

    def dbSave(self):
        Db.instance().store(self.key, self.serialize())

    def __str__(self):
        if len(self.players) == 2:
            return "Game. key: {}, players: [{}, {}]".format(self.key, self.players[0], self.players[1])
        elif len(self.players) == 1:
            return "Game. key: {}, players: [{}]".format(self.key, self.players[0])
        else:
            return "Game. key: {}, players: []".format(self.key)

    def checkIfPlayersActive(self):
        if self.state != GameState.active:
            return

        if None in self.players or len(self.players) < 2:
            self.players.remove(None)
            self.state = GameState.playerLeft
            self.stateFrame += 1

    def addPlayer(self, player):
        self.players.append(player)
        if len(self.players) == 2:
            self.state = GameState.active
            self.activePlayer = choice(self.players)
            self.stateFrame += 1

    def removePlayer(self, player):
        try:
            self.players.remove(player)
            if self.state == GameState.active:
                self.state = GameState.playerLeft
        except ValueError:
            pass

    def makeMove(self, player, cellIndx):
        if self.state != GameState.active or player != self.activePlayer:
            return False

        gridIndx = 3 * cellIndx[1] + cellIndx[0]
        if self.grid[gridIndx] == '':
            self.grid[gridIndx] = self._getPlayerToken(player)
        else:
            return False
        self.update()
        return True

    def hasUpdatesForPlayer(self, player):
        self = Game(self.key)
        return self.stateFrame != player.knownGameState

    def getStateDict(self, player):
        otherPlayer = self.otherPlayer(player)
        retD = {
            "playerId": player.key,
            "competitorId": otherPlayer.key if otherPlayer is not None else None,
            "state": self.state.name,
            "isYourTurn": self.activePlayer == player,
            "yourToken": 'o' if player == self.players[0] else 'x',
            "grid": [self.grid[0:3], self.grid[3:6], self.grid[6:9]],
            "stateFrame": self.stateFrame,
            "yourStateFrame": player.knownGameState,
        }
        if self.state == GameState.finished:
            retD["winner"] = self.winner == player if self.winner is not None else None
        return retD

    def gridString(self):
        string = ''
        for y in range(3):
            for x in range(3):
                token = self.grid[y * 3 + x]
                if token == '':
                    token = '+'
                string += token

            string += '\n'
        return string

    def otherPlayer(self, player):
        if len(self.players) < 2:
            return None
        if player == self.players[0]:
            return self.players[1]
        elif player == self.players[1]:
            return self.players[0]

    def update(self):
        # check if anyone won
        if self.state == GameState.active:
            winner = self._getWinner()
            if (winner in self.players) or ('' not in self.grid):
                self.state = GameState.finished
                self.winner = winner
            if self.activePlayer == self.players[0]:
                self.activePlayer = self.players[1]
            else:
                self.activePlayer = self.players[0]
        self.stateFrame += 1
        self.dbSave()

    def _getPlayerToken(self, player):
        assert player in self.players
        if player == self.players[0]:
            return 'o'
        else:
            return 'x'

    def _getWinner(self):
        if self._isWinner('o'):
            return self.players[0]
        elif self._isWinner('x'):
            return self.players[1]
        else:
            return None

    def _isWinner(self, token):
        return (
            # horizontal
            not (not (self.grid[0] == token and self.grid[1] == token and self.grid[2] == token) and not (
                self.grid[3] == token and self.grid[4] == token and self.grid[5] == token) and not (
                self.grid[6] == token and self.grid[7] == token and self.grid[8] == token) and not (
                self.grid[0] == token and self.grid[3] == token and self.grid[6] == token) and not (
                self.grid[1] == token and self.grid[4] == token and self.grid[7] == token)) or
            (self.grid[2] == token and self.grid[5] == token and self.grid[8] == token) or
            # diagonal
            (self.grid[0] == token and self.grid[4] == token and self.grid[8] == token) or
            (self.grid[2] == token and self.grid[4] == token and self.grid[6] == token)
        )


class Player:
    def __init__(self, playerId=None, gameInst=None, knownGameState=0):
        self.key = playerId  # app-wide unique key
        if knownGameState is not None:
            self.knownGameState = knownGameState  # increments as player receives updates
        else:
            self.knownGameState = 0
        self.game = None  # the game this player currently bound to

        db = Db.instance()
        # Generate key if needed
        if self.key is None:
            self.key = db.generateKey()
        # Check if player with such key exists. If he does, retrieve his
        # info from db. If he does not, create him
        if db.keyExists(self.key):
            self.deserialize(db.retrieve(self.key), gameInst)
        else:
            db.store(self.key, self.serialize())

    def serialize(self):
        obj = {
            "key": self.key,
            #"knownGameState": self.knownGameState,
            "gameKey": self.game.key if self.game is not None else None
        }
        return json.dumps(obj).encode('UTF8')

    def deserialize(self, objStr, gameInst=None):
        obj = json.loads(objStr.decode('UTF8'))
        self.key = obj["key"]
        #self.knownGameState = obj["knownGameState"]
        if gameInst is not None:
            self.game = gameInst
        else:
            if obj['gameKey'] is not None and Db.instance().keyExists(obj["gameKey"]):
                self.game = Game(obj["gameKey"])
            else:
                self.game = None

    def startOrJoinGame(self):
        # If the player is already taking part in some game, remove him from it
        if self.game is not None:
            self.game.removePlayer(self)
        self.reset()
        self.game = Game.findNew(self)

    def reset(self):
        """
		Resets player state so that he could join new game
		"""
        self.knownGameState = 0
        self.game = None

    def dbSave(self):
        """
		This method is called whenever player state needs to be saved in database
		"""
        Db.instance().store(self.key, self.serialize())

    def __str__(self):
        return "Player key: {}".format(self.key)

    def __eq__(self, other):
        return other is not None and self.key == other.key


def cleanup():
    """
	This function should run in separate greenlet with some time interval.
	It iterates through games queue and checks if they have at least one player.
	If they dont, it removes given games from list
	"""
    db = Db.instance()
    numCleaned = 0
    gamesQueue = db.retrieveList(GAME_WAITING_QUEUE)
    if gamesQueue is None:
        return
    for gameKey in gamesQueue:
        game = Game(gameKey)
        if len(game.players) == 0:
            db.removeFromList(GAME_WAITING_QUEUE, gameKey)
            numCleaned += 1
    return numCleaned


def main():
    pass


if __name__ == '__main__':
    main()
