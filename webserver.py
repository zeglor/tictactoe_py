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

from gevent import sleep, monkey
monkey.patch_all()
from gevent.wsgi import WSGIServer
from flask import Flask, session, request, render_template, jsonify
from game import Game, GameController, GameState, Player, Result
from random import randint

app = Flask(__name__)
app.secret_key = b'\xd0X\xb3\x89\xcf\xef\xd4\x04\xd4c\xa4\xed\x88\xe4\x91B(\x93\xdd\xa2L\xde=k\x9d'

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
	playerAction = data.get('action')
	cell = [int(data.get('cellCol')), int(data.get('cellRow'))]
	if playerAction == 'put':
		gameInst = GameController.getGameByPlayer(player)
		gameInst.processData(player, cell)
		return jsonify(status='ok')

@app.route("/sub/", methods=["POST", "GET"])
def sub():
	player = initPlayer()
	
	gameInst = GameController.getOrCreateGame(player)
	if request.method == "GET":
		return jsonify(gameInst.getStateDict(player))
	# at this point game with two players has started
	while (not gameInst.hasUpdatesForPlayer(player)) and (gameInst.state != GameState.finished):
		sleep(0.1)
	if (session.get("id") is None) or (session["id"] != player.key):
		session["id"] = player.key
	player.updateKnownState(gameInst)
	return jsonify(gameInst.getStateDict(player))

@app.route("/")
def index():
	return render_template('tictactoe.html')


if __name__ == '__main__':
	http_server = WSGIServer(('', 8080), app)
	http_server.serve_forever()
