#! /usr/bin/python3
import os
import sys
import time # for sleep
import logging # for logging
import datetime # for logging
import traceback # for error handling
import subprocess # for executing bash commands
import configparser # for configuration parser
# Local
import bot
##### Constants #####
currentDir = os.getcwd()
configFile = "./configuration.cfg"
configSection = "configuration"

# Logging function
def getLogger():
  # Create logs folder if not exists
  if not os.path.isdir(os.path.join(currentDir, "logs")):
    try:
      os.mkdir(os.path.join(currentDir, "logs"))
    except OSError:
      print("Creation of the logs directory failed")
    else:
      print("Successfully created the logs directory")

  now = datetime.datetime.now()
  log_name = "" + str(now.year) + "." + '{:02d}'.format(now.month) + "." + '{:02d}'.format(now.day) + "-backtester.log"
  log_name = os.path.join(currentDir, "logs", log_name)
  logging.basicConfig(format='%(asctime)s  %(message)s', level=logging.NOTSET,
                      handlers=[
                      logging.FileHandler(log_name),
                      logging.StreamHandler()
                      ])
  log = logging.getLogger()
  return log

def executeCommand(command):
  error = ""
  output = ""
  ("Executing: " + command)
  try:
    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    output = output.decode('utf-8')
    #print("Output: " + output)
  except Exception as e:
    error = "ERROR: " + str(e.returncode) + "  " + str(e) + "\n"

  return output, error


def mainFunction():
  log = getLogger()
  log.info("################################# New run backtester")
  try:
    # Check if configuration file exists, and exit if it is not
    if os.path.isfile(configFile) is False:
      message = "[FATAL] Config file does not exist. Exiting"
      log.info(message)
      sys.exit(1)

    # Read config file
    configObj = configparser.ConfigParser()
    configObj.read(configFile)
    global config
    config = configObj._sections[configSection]

    backtesting_start_timestamp = config["backtesting_start_timestamp"]

    # Run bot
    log.info("#### Run bot")
    #output = executeCommand("python3 bot.py")
    bot.mainFunction()
    # Run plotter
    log.info("#### Run plotter")
    filename = "backtester-" + config["backtesting_start_timestamp"] + "-" + config["backtesting_end_timestamp"] + ".html"
    output, error = executeCommand("python3 plotter.py " + filename + " " + config["backtesting_start_timestamp"] + " " + config["backtesting_end_timestamp"])
    log.info(error)

  ##### END #####
  except KeyboardInterrupt:
    log.info("Ctrl+C received. Gracefully quiting.")
    sys.exit(0)
  except Exception as e:
    log.info("Fatal Error: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)
    sys.exit(99)

##### BODY #####
if __name__ == "__main__":

  if len(sys.argv) != 1:
    log.info("Wrong number of parameters. Use: python backtester.py")
    sys.exit(99)
  else:
    mainFunction()