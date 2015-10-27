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
#  

from gevent import sleep, monkey, spawn
monkey.patch_all()
from gevent.wsgi import WSGIServer
from flask import Flask, session, request, render_template, jsonify
from game import Game, GameState, Player, cleanup
from random import randint
from datetime import datetime
from secret import secret_key

POLL_TIMEOUT = 5

app = Flask(__name__)
app.debug = True
app.secret_key = secret_key

def initPlayer():
	playerId = session.get('id')
	data = request.get_json()
	knownState = data.get('knownState')
	player = Player.initialize(playerId, knownState)
	return player

@app.route("/pub/", methods=["POST"])
def pub():
	player = initPlayer()
	data = request.get_json()
	cell = None
	playerAction = data.get('action')
	if playerAction == 'put':
		cell = [int(data.get('cellCol')), int(data.get('cellRow'))]
		gameInst = GameController.getGameByPlayer(player)
		gameInst.processData(player, cell)
		return jsonify(status='ok')
	elif playerAction == 'startNew':
		print("starting new game")
		gameInst = GameController.startNewGame(player)
		return jsonify(status='ok')

@app.route("/sub/", methods=["POST", "GET"])
def sub():
	player = initPlayer()
	
	gameInst = GameController.getOrCreateGame(player)
	if request.method == "GET":
		return jsonify(gameInst.getStateDict(player))
	# at this point game with two players has started
	pollTime = datetime.now()
	while (not gameInst.hasUpdatesForPlayer(player)) and \
		(gameInst.state != GameState.finished) and \
		(gameInst.state != GameState.playerDisconnected) and \
		((datetime.now() - pollTime).total_seconds() < POLL_TIMEOUT):
		sleep(0.1)
	# at this point player could already be cleaned up
	if (session.get("id") is None) or (session["id"] != player.key):
		session["id"] = player.key
	player.updateKnownState(gameInst)
	if (datetime.now() - pollTime).total_seconds() >= POLL_TIMEOUT and \
		(gameInst.state in (GameState.active, GameState.waitingPlayers)):
		return jsonify(state="pollTimeout")
	return jsonify(gameInst.getStateDict(player))

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
