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

from gevent import monkey
monkey.patch_all()
from enum import Enum
from collections import deque
from random import choice
from uuid import uuid4

class GameState(Enum):
	waitingPlayers = 1
	active = 2
	finished = 3

class Result(Enum):
	ok = 1
	error = 2
	
class Game:
	def __init__(self, player):
		self.players = [player, None] 		# player[0] is 'o', player[1] is 'x'
		self.activePlayer = None			# whose turn is now?
		self.grid = ['' for _ in range(9)]	# 3x3 game grid
		self.state = GameState.waitingPlayers
		# This variable is needed to keep in sync with both players. It is
		# incremented each time game state is updated (e.g. player makes a move).
		# Each player stores his value of stateFrame, so if player's copy is
		# less than game's, his game state is outdated
		self.stateFrame = 1
		self.winner = None
	
	def addPlayer(self, player):
		self.players[1] = player
		self.state = GameState.active
		# choose player to make first move
		self.activePlayer = choice(self.players)
		self._updateGame()
	
	def makeMove(self, player, cellIndx):
		if self.state != GameState.active or player != self.activePlayer:
			return Result.error
		
		gridIndx = 3 * cellIndx[1] + cellIndx[0]
		if self.grid[gridIndx] == '':
			self.grid[gridIndx] = self._getPlayerToken(player)
			self._updateGame()
			return Result.ok
		return Result.error
	
	def processData(self, player, move):
		if self.state == GameState.waitingPlayers:
			if player[0] != player:
				self.addPlayer(player)
				return Result.ok
			else:
				return Result.error
		elif self.state == GameState.active:
			self.makeMove(player, move)
			return Result.ok
		else:
			return Result.error
	
	def hasUpdatesForPlayer(self, player):
		return self.stateFrame > player.knownGameState
	
	def getStateDict(self, player):
		competitorId = None
		if self.players[0] == player:
			competitorId = self.players[1].key if self.players[1] is not None else None
		else:
			competitorId = self.players[0].key
		retD = {
			"playerId": player.key,
			"competitorId": competitorId,
			"state": self.state.name,
			"isYourTurn": self.activePlayer == player,
			"yourToken": 'o' if player == self.players[0] else 'x',
			"grid": [self.grid[0:3], self.grid[3:6], self.grid[6:9]],
			"stateFrame": self.stateFrame,
		}
		if self.state == GameState.finished:
			retD["winner"] = (player == self.winner)
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
	
	def _updateGame(self):
		# check if anyone won
		winner = self._getWinner()
		if (winner in self.players) or ('' not in self.grid):
			self.state = GameState.finished
			self.winner = self._getWinner()
		if self.activePlayer == self.players[0]:
			self.activePlayer = self.players[1]
		else:
			self.activePlayer = self.players[0]
		self.stateFrame += 1
	
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
			#horizontal
			(self.grid[0] == token and self.grid[1] == token and self.grid[2] == token) or
			(self.grid[3] == token and self.grid[4] == token and self.grid[5] == token) or
			(self.grid[6] == token and self.grid[7] == token and self.grid[8] == token) or
			#vertical
			(self.grid[0] == token and self.grid[3] == token and self.grid[6] == token) or
			(self.grid[1] == token and self.grid[4] == token and self.grid[7] == token) or
			(self.grid[2] == token and self.grid[5] == token and self.grid[8] == token) or
			#diagonal
			(self.grid[0] == token and self.grid[4] == token and self.grid[8] == token) or
			(self.grid[2] == token and self.grid[4] == token and self.grid[6] == token)
		)

class GameController:
	gameList = []
	gamesByPlayer = {}
	gamesWaiting = deque()
	
	def __init__(self):
		pass
	
	@staticmethod
	def getOrCreateGame(player):
		gameInst = GameController.gamesByPlayer.get(player.key)
		if gameInst is None:
			if len(GameController.gamesWaiting) == 0:
				gameInst = Game(player)
				GameController.gamesWaiting.appendleft(gameInst)
				GameController.gameList.append(gameInst)
				GameController.gamesByPlayer[player.key] = gameInst
			else:
				gameInst = GameController.gamesWaiting.pop()
				GameController.gamesByPlayer[player.key] = gameInst
				gameInst.addPlayer(player)
		return gameInst
	
	@staticmethod
	def getGameByPlayer(player):
		gameInst = GameController.gamesByPlayer.get(player.key)
		return gameInst
	
class Player:
	knownIds = set()
	knownGameStates = {}
	def __init__(self, playerId=None):
		self.key = playerId			# app-wide unique key
		self.knownGameState = 0	# increments as player receives updates
		if self.key is None:
			self.key = Player._makeUniqueKey()
			Player.knownIds.add(self.key)
			self.knownGameState = 0
		else:
			self.knownGameState = Player.knownGameStates[self.key]
	
	@staticmethod
	def initialize(playerId=None, knownState = None):
		if (playerId is not None) and (playerId in Player.knownIds):
			player = Player(playerId)
		else:
			player = Player()
		return player
	
	@staticmethod
	def _makeUniqueKey():
		return uuid4()
	
	def updateKnownState(self, game):
		self.knownGameState = game.stateFrame
		Player.knownGameStates[self.key] = self.knownGameState
	
	def __eq__(self, other):
		if (other is not None) and (self.key == other.key):
			return True
		else:
			return False
	
	def __str__(self):
		return str(self.key)

def main():
	player = Player.initialize()
	gameInst = GameController.getOrCreateGame(player)
	print(gameInst)
	
	player2 = Player.initialize()
	gameInst = GameController.getOrCreateGame(player2)
	print(gameInst)
	print(gameInst.players)
	
	print(gameInst.activePlayer)
	# one of these moves should be valid
	res = gameInst.makeMove(player, [0,0])
	print(res)
	res = gameInst.makeMove(player2, [0,0])
	print(res)
	print(gameInst.gridString())
	print(gameInst.activePlayer)
	activePlayer = gameInst.activePlayer
	res = gameInst.makeMove(activePlayer, [0,1])
	activePlayer = gameInst.activePlayer
	res = gameInst.makeMove(activePlayer, [1,1])
	activePlayer = gameInst.activePlayer
	res = gameInst.makeMove(activePlayer, [0,2])
	print(gameInst.gridString())
	activePlayer = gameInst.activePlayer
	res = gameInst.makeMove(activePlayer, [2,2])
	print(gameInst.gridString())
	print(gameInst.winner)
	print(gameInst.state)
	
	return 0

if __name__ == '__main__':
	main()

