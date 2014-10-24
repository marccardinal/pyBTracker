#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# **********
# Filename:         pyBTracker.py
# Description:      A simple tornado bittorrent tracker in python
# Author:           Marc Vieira Cardinal
# Creation Date:    July 08, 2014
# Revision Date:    August 06 22, 2014
# **********

# TODO: IP acl?


# External imports
import sys
import shelve
from argparse import ArgumentParser

# Application imports
import LogUtils
from Tracker import Tracker


#############
# Main
###

if __name__ == "__main__":

    # Parse the command line arguments
    # Define the main parser (top-level)
    argParser = ArgumentParser()
    argParser.add_argument("-b", "--bind",
                           dest    = "bind",
                           action  = "store",
                           default = "127.0.0.1",
                           help    = "Bind ip to listen on")
    argParser.add_argument("-p", "--port",
                           dest    = "port",
                           action  = "store",
                           default = 1337,
                           type    = int,
                           help    = "Set the tcp port to listen on")
    argParser.add_argument("-i", "--interval",
                           dest    = "interval",
                           action  = "store",
                           default = 5,
                           type    = int,
                           help    = "Tracking interval in seconds")
    argParser.add_argument("-m", "--min-interval",
                           dest    = "minInterval",
                           action  = "store",
                           default = 2,
                           type    = int,
                           help    = "Minimum accepted tracking interval in seconds")
    argParser.add_argument("-f", "--foreground",
                           dest    = "foreground",
                           action  = "store_true",
                           default = False,
                           help    = "Run in foreground")
    argParser.add_argument("-l", "--loglevel",
                           dest    = "logLevel",
                           choices = ["notset", "debug", "info",
                                      "warning", "error", "critical"],
                           default = "notset",
                           help    = "Logging level")
    argParser.add_argument("-o", "--logfile",
                           dest    = "logFile",
                           action  = "store",
                           default = "/tmp/pyBTracker.log",
                           help    = "Log file")
    argParser.add_argument("-d", "--db",
                           dest    = "dbFile",
                           action  = "store",
                           default = "pyBTracker.db",
                           help    = "DB (state) file")
    args = vars(argParser.parse_args())

    logger = LogUtils.RotatingFile(__name__,
                                   args["logLevel"],
                                   args["logFile"],
                                   args["foreground"])
    logger.info("Started with arguments: " + str(args))

    if len(args["dbFile"]) > 0:
        db = shelve.open(args["dbFile"], "c", writeback = True)
    else:
        db = dict()

    tracker = Tracker(logger,
                      db,
                      args["bind"],
                      args["port"],
                      args["interval"],
                      args["minInterval"])
    try:
        logger.info("Starting tracker")
        tracker.Start()
    except KeyboardInterrupt:
        tracker.Stop()
        logger.info("Stopped")
        sys.exit(0)
    except Exception, e:
        logger.error("Caught exception: " + str(e))
        sys.exit(1)
