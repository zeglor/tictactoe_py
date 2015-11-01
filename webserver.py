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
from game import Player, cleanup
from random import uniform as randUniform
from datetime import datetime
from secret import secret_key

POLL_TIMEOUT = 5


class RemotePlayer:
    def __init__(self, session, request):
        playerKey = session.get("id")
        knownGameState = request.get_json().get("knownGameState")
        self.player = Player(playerKey, None, knownGameState)
        session["id"] = self.player.key
        self.player.dbSave()
        #if self.player.game is not None:
        #    self.player.game.dbSave()

    def __enter__(self):
        return self.player

    def __exit__(self, type, value, traceback):
        self.player.dbSave()


app = Flask(__name__)
#app.debug = True
app.secret_key = secret_key


@app.route("/pub/", methods=["POST"])
def pub():
    with RemotePlayer(session, request) as player:
        data = request.get_json()
        action = data.get("action")
        #print("got request of type {}".format(action))

        # process requested action
        if action == "heartbeat":
            #print("heartbeat from {}".format(player))
            # player gets automatically updated after request is finished
            # we should store only game state
            if player.game is not None:
                player.game.dbSave()
        elif action == "joinGame":
            #print('joining game: {}'.format(player))
            # pdb.set_trace()
            player.startOrJoinGame()
        elif action == "move":
            #print("making move: {}".format(player))
            cellIndex = [int(indx) for indx in data.get("cell")]
            player.game.makeMove(player, cellIndex)
    return jsonify({'status': 'ok'})


@app.route("/sub/", methods=["POST"])
def sub():
    def timeoutPassed(pollTime):
        return (datetime.now() - pollTime).total_seconds() >= POLL_TIMEOUT

    with RemotePlayer(session, request) as player:
        game = player.game
        if game is None:
            return jsonify({"type": "error", "reason": "not_connected"})
        try:
            isUrgentMessage = request.get_json()["urgent"]
        except KeyError:
            isUrgentMessage = False
        pollTime = datetime.now()
        while (not game.hasUpdatesForPlayer(player)) and (not timeoutPassed(pollTime)) and not isUrgentMessage:
            sleep(randUniform(0.03, 0.3))
        # now we either have updates for player, or timeout passed, or player requested immediate update
        if timeoutPassed(pollTime):
            return jsonify({"type": "timeout"})
        else:
            # make message
            msg = game.getStateDict(player)
            msg["type"] = "event"
            return jsonify(msg)


@app.route("/")
def index():
    return render_template('tictactoe.html')

def cleanup_forever():
    while (True):
        sleep(60)
        cleanup()


if __name__ == '__main__':
    spawn(cleanup_forever)
    http_server = WSGIServer(('', 8080), app)
    http_server.serve_forever()
