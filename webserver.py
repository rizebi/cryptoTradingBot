import os
import time
import subprocess # for executing bash commands
import configparser # for configuration parser
from flask import Flask, render_template, send_from_directory

from plotter import mainFunction

##### Variables #####
app = Flask(__name__)
configFile = "./configuration.cfg"
configSection = "configuration"

def executeCommand(command):
  error = ""
  output = ""
  print("Executing: " + command)
  try:
    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    output = output.decode('utf-8')
    #print("Output: " + output)
  except Exception as e:
    error = "ERROR: " + str(e.returncode) + "  " + str(e) + "\n"

  return output, error


# Paths for graphs
@app.route('/')
def historyFull():
  # Create plot
  output = executeCommand("python3 plotter.py index0.html yes 0 3000000000")
  # Return plot
  return render_template('index0.html')

@app.route('/<number>m')
def historyMinutes(number):
  currentTime = time.time()
  wantedTime = int(time.time() - (int(number) * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index" + str(number) + "m.html yes " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template("index" + str(number) + "m.html")

@app.route('/notrades/<number>m')
def historyMinutesNoTrades(number):
  currentTime = time.time()
  wantedTime = int(time.time() - (int(number) * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index" + str(number) + "m.html no " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template("index" + str(number) + "m.html")

@app.route('/<number>h')
def historyHours(number):
  currentTime = time.time()
  wantedTime = int(time.time() - (int(number) * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index" + str(number) + "h.html yes " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template("index" + str(number) + "h.html")

@app.route('/notrades/<number>h')
def historyHoursNoTrades(number):
  currentTime = time.time()
  wantedTime = int(time.time() - (int(number) * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index" + str(number) + "h.html no " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template("index" + str(number) + "h.html")

@app.route('/<number>d')
def historyDays(number):
  currentTime = time.time()
  wantedTime = int(time.time() - (int(number) * 24 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index" + str(number) + "d.html yes " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template("index" + str(number) + "d.html")

@app.route('/notrades/<number>d')
def historyDaysNoTrades(number):
  currentTime = time.time()
  wantedTime = int(time.time() - (int(number) * 24 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index" + str(number) + "d.html no " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template("index" + str(number) + "d.html")

# Path for database
@app.route('/database')
def getDatabase():
  configObj = configparser.ConfigParser()
  configObj.read(configFile)
  config = configObj._sections[configSection]
  currentDir = os.getcwd()
  databaseFile = os.path.join(currentDir, config["database_file"])
  #return databaseFile
  return send_from_directory(directory="/".join(databaseFile.split("/")[:-1]), filename=databaseFile.split("/")[-1])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')