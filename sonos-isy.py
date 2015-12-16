#!/usr/bin/python
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2014 VictorOps, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ------------------------------------------------------------------------------
#
# This script was originally created by VictorOps and released under the MIT 
# license.  It has been heavily modified for use on a Universal Devices ISY994i.
#
# Runs a local micro web server (daemon) to listen for calls from an ISY device.
# A call requests a Sonos player on the local network to play an alert sound
# when triggered by the ISY and then return to playing music.  
#
#
# Requires:
#     SoCo     https://github.com/SoCo/SoCo
#     Flask    https://github.com/mitsuhiko/flask
#     URL      The sonos is told to retrieve a file from a URL to play.
#              This may be an http source or a NAS or an nginx server running
#              on the same server as this script. 
#              (Serving static file via this script was painfully slow, avoid it)
#
# You may also find helpful:
#     ngrok    https://ngrok.com/
#
# ------------------------------------------------------------------------------

import sys
import soco
import time
import hmac
import hashlib
import base64
import ConfigParser
from soco import SoCo
from flask import Flask
from flask import request 

if len(sys.argv) < 2:
    print """
    USAGE: %s <config file>"
    """ % sys.argv[0]
else:

    # 0:03:18 -> 198
    def timeToInt( timeStr ):
        accum = 0
        mult = 1
        for p in reversed(timeStr.split(':')):
            accum += (int(p)*mult)
            mult *= 60
        return accum

    # Read the config file
    config = ConfigParser.ConfigParser()
    config.read(sys.argv[1])
    sonosPlayer = config.get('sonos-alerts', 'sonosPlayer')
    alertSoundURL = config.get('sonos-alerts', 'alertSoundURL')
    alertWebhookURL = config.get('sonos-alerts', 'alertWebhookURLRoot')
    alertWebhookAuthKey = config.get('sonos-alerts', 'alertWebhookAuthKey')
    listenPort = int(config.get('sonos-alerts','listenPort'))

    # Connect to the player
    sonos = None

    sonos = SoCo(sonosPlayer)
    
    print 'Connected to Sonos %s' % sonosPlayer
    
    # ISY will POST trigger this path
    app = Flask(__name__)
    @app.route('/doorbellpress', methods=['POST'])    
    def doorbellPress():    

        #! debug
        #sonosAction = request.headers['SonosAction']
        print 'query string is %s' % request.query_string
        #print 'sonosaction is %s' % sonosAction

        # Find out if the player is playing or not (e.g. don't need to resume if it isn't)
        playbackState = sonos.get_current_transport_info()
        print 'Playback state is %s' % playbackState['current_transport_state']

        # Get our player resume position so we can resume after playing
        # the alert sound.    
        if playbackState['current_transport_state'] == 'PLAYING':        
            track = sonos.get_current_track_info()
            playlistPos = int(track['playlist_position'])-1
            trackPos = track['position']
            trackURI = track['uri']

            # This information allows us to resume services like Pandora
            mediaInfo = sonos.avTransport.GetMediaInfo([('InstanceID', 0)])
            mediaURI = mediaInfo['CurrentURI']
            mediaMeta = mediaInfo['CurrentURIMetaData']

        # Play the alert sound, and sleep to allow it to play through
        #???? to do: consider setting volume level and then restoring it?
        print 'Notifying sonos to play %s' % alertSoundURL
        sonos.play_uri(alertSoundURL)
        alertDuration = sonos.get_current_track_info()['duration']
        #sleepTime = timeToInt(alertDuration) + 2
        sleepTime = timeToInt(alertDuration)
        time.sleep(sleepTime)

        if playbackState['current_transport_state'] == 'PLAYING':
            print "Restarting music..."
            # TODO: Fix resuming Pandora (and other services?) playback
            if len(sonos.get_queue()) > 0 and playlistPos > 0:
              print 'Resume queue from %d: %s - %s' % (playlistPos, track['artist'], track['title'])
              sonos.play_from_queue(playlistPos)
              sonos.seek(trackPos)
            else:
              print 'Resuming %s' % mediaURI
              sonos.play_uri(mediaURI, mediaMeta)
            
        return "OK"
        
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=listenPort, debug=True)
