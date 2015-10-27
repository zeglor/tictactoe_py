#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  webserver.py
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

# Player message looks something like that: {"action": action_requested}
# What messages is player able to send us:
# * Report that he's still online (should not be called that often)		{"action": "heartbeat"}
# * Request a new game to join											{"action": "joinGame" }
# * Report his move														{"action": "move", "cell": [x, y]}

from gevent import sleep, monkey, spawn
monkey.patch_all()
from gevent.wsgi import WSGIServer
from flask import Flask, session, request, render_template, jsonify
from game import Game, GameState, Player, cleanup
from random import randint
from datetime import datetime
from secret import secret_key

POLL_TIMEOUT = 5

class RemotePlayer:
	def __init__(self, session):
		playerKey = session.get("id")
		self.player = Player(playerKey)
		session["id"] = self.player.key
		self.player.dbSave()
		if self.player.game is not None:
			self.player.game.dbSave()
	
	def __enter__(self):
		return self.player
	
	def __exit__(self, type, value, traceback):
		self.player.dbSave()
		if self.player.game is not None:
			self.player.game.dbSave()

app = Flask(__name__)
app.debug = True
app.secret_key = secret_key

@app.route("/pub/", methods=["POST"])
def pub():
	with RemotePlayer(session) as player:
		data = request.get_json()
		action = data.get("action")
		
		#process requested action
		if action == "heartbeat":
			print("heartbeat from {}".format(player))
			# player gets automatically updated after request is finished
			pass
		elif action == "joinGame":
			print("joining game: {}".format(player))
			player.startOrJoinGame()
		elif action == "move":
			print("making move: {}".format(player))
			cellIndex = data.get("cell")
			player.game.makeMove(player, cellIndex)
	return 'OK'

@app.route("/sub/", methods=["POST"])
def sub():
	def timeoutPassed():
		return (datetime.now() - self.pollTime).total_seconds() >= POLL_TIMEOUT
	
	with RemotePlayer(session) as player:
		game = player.game
		if game is None:
			return jsonify({"type": "error", "reason": "not_connected"})
		timeoutPassed.pollTime = datetime.now()
		while (not game.hasUpdatesForPlayer(player)) and (not timeoutPassed()):
			sleep(0.1)
		# now we either have updates for player, or timeout passed
		if timeoutPassed():
			return jsonify({"type": "timeout"})
		else:
			msg = gameInst.getStateDict(player)
			msg["type"] = "event"
			return jsonify(msg)

@app.route("/")
def index():
	return render_template('tictactoe.html')


def cleanup_forever():
	while(True):
		sleep(2)
		cleanup()

if __name__ == '__main__':
	spawn(cleanup_forever)
	http_server = WSGIServer(('', 8080), app)
	http_server.serve_forever()
