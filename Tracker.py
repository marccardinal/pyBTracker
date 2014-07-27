#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# **********
# Filename:         Tracker.py
# Description:      The business end of the tornado based tracker
# Author:           Marc Vieira Cardinal
# Creation Date:    July 08, 2014
# Revision Date:    July 21, 2014
# Resources:
#   https://wiki.theory.org/BitTorrentSpecification
#   https://wiki.theory.org/BitTorrent_Tracker_Protocol
# **********


# External imports
import sys
import json
import logging
import tornado.ioloop
import tornado.web
import tornado.httpserver


# Application imports
from socket import inet_aton
from struct import pack
from bencode import bencode, bdecode


def GeneratePeerList(infoHashObj, compact, numWant, noPeerId):
    if compact:
        peers = ""

        for peer, value in infoHashObj.items():
            peers += ( inet_aton(value[0]) +
                       pack(">H", int(value[1])) )
        return peers[:numWant*6]
    else:
        peers = []

        for peer, value in infoHashObj.items():
            peer = {"ip": value[0], "port": value[1]}

            if noPeerId == 0:
                peer["peer id"] = peer

            peers.append(peer)
        return peers[:numWant]


class Tracker():
    def __init__(self, logger, db, bind, port, interval, minInterval):
        self.logger      = logger.getChild(__name__)
        self.db          = db
        self.bind        = bind
        self.port        = port
        self.config    = {
            "interval":    interval,
            "minInterval": minInterval
        }

    def Start(self):
        TrackerApp(self.logger, self.db, self.config).listen(self.port, self.bind)
        tornado.ioloop.IOLoop.instance().start()

    def Stop(self):
        pass


class TrackerApp(tornado.web.Application):
    def __init__(self, logger, db, config):

        super(TrackerApp, self).__init__([
            (r"/announce",   TrackerAnnounce,   dict(logger   = logger,
                                                     config   = config,
                                                     db       = db)),
            (r"/scrape",     TrackerScrape,     dict(logger   = logger,
                                                     config   = config,
                                                     db       = db)),
            (r"/scrapeJson", TrackerScrapeJson, dict(logger   = logger,
                                                     config   = config,
                                                     db       = db)),
            (r"/torrents",   TrackerTorrents,   dict(logger   = logger,
                                                     config   = config,
                                                     db       = db)),
            ])


class TrackerAnnounce(tornado.web.RequestHandler):
    def initialize(self, logger, config, db):
        self.logger = logger
        self.config = config
        self.db     = db

    def get(self):
        # Err handling containers
        failMessage = ""
        WarnMessage = ""

        # Process the mandatory arguments
        infoHash   = self.get_argument("info_hash",  None)
        peerId     = self.get_argument("peer_id",    None)
        peerPort   = self.get_argument("port",       None)
        peerIp     = self.get_argument("ip",         self.request.remote_ip)

        # Validation
        if not infoHash:
            return self.send_error(101) # Missing info_hash
        if not peerId:
            return self.send_error(102) # Missing peer_id
        if not peerPort:
            return self.send_error(103) # Missing port
        if len(infoHash) != 20:
            return self.send_error(150) # Invalid infohash: infohash is not 20 bytes long
        if len(peerId) != 20:
            return self.send_error(151) # Invalid peerid: peerid is not 20 bytes long

        # Process optional arguments
        uploaded   = self.get_argument("uploaded",   0)  # Optional
        downloaded = self.get_argument("downloaded", 0)  # Optional
        left       = self.get_argument("left",       0)  # Optional
        event      = self.get_argument("event",      "") # Optional
        numWant    = self.get_argument("numwant",    50) # Optional
        noPeerId   = self.get_argument("no_peer_id", 0)  # Optional
        compact    = self.get_argument("compact",    0)  # Optional
        trackerId  = self.get_argument("trackerid",  "") # Optional

        # Additional validation
        if numWant > 100:
            self.send_error(152) # Invalid numwant. Client requested more peers than allowed by tracker

        if event:
            if not infoHash in self.db:
                self.db["tracking"][infoHash] = { peerId: (peerIp, peerPort, event) }
            else:
                self.db["tracking"][infoHash][peerId] = (peerIp, peerPort, event)

        self.set_header("content-type", "text/plain")
        if failMessage:
            # If present, the failure message must be alone
            self.write(bencode({
                "failure reason": failMessage
                }))
        else:
            retObj = {
                "interval":     self.config["interval"],
                "min_interval": self.config["minInterval"],
                "complete":     len([(k, v) for k, v in self.db["tracking"][infoHash].items() if v[2] == "completed"]),
                "incomplete":   len([(k, v) for k, v in self.db["tracking"][infoHash].items() if v[2] == "started"]),
                "peers":        GeneratePeerList(self.db["tracking"][infoHash],
                                                 compact,
                                                 numWant,
                                                 noPeerId),
                }

            if trackerId:
                retObj["tracker id"] = trackerId

            # Include the optional warning message
            if warnMessage:
                retObj["warning message"] = warnMessage

            self.write(bencode(retObj))


class TrackerScrape(tornado.web.RequestHandler):
    def initialize(self, logger, config, db):
        self.logger = logger
        self.config = config
        self.db     = db

    def get(self):
        self.write("not implemented...")
        self.set_status(200)


class TrackerScrapeJson(tornado.web.RequestHandler):
    def initialize(self, logger, config, db):
        self.logger = logger
        self.config = config
        self.db     = db

    def get(self):
        self.set_status(200)
        self.set_header("content-type", "application/json")
        self.write(json.dumps(self.db["tracking"]))


class TrackerTorrents(tornado.web.RequestHandler):
    def initialize(self, logger, config, db):
        self.logger = logger
        self.config = config
        self.db     = db

    def get(self):
        self.logger.info("Reached TrackerTorrents.get")
        key = self.get_argument("key")

        if key in self.db["torrents"]:
            self.logger.info("Returning file [key:%s][size:%s]" % (key,
                                                                   len(self.db["torrents"][key])))
            self.set_status(200)
            self.write(self.db["torrents"][key])
        else:
            self.logger.info("A file for [key:%s] was not found" % key)
            self.set_status(404)

    def post(self):
        self.logger.info("Reached TrackerTorrents.post")

        for fileInfo in self.request.files["torrentFile"]:
            self.logger.info("Processing file [key:%s][size:%s]" % (fileInfo["filename"],
                                                                    len(fileInfo["body"])))
            self.db["torrents"][fileInfo["filename"]] = fileInfo["body"]

        self.set_status(200)
