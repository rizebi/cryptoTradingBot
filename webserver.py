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
  output = executeCommand("python3 plotter.py index0.html 0 3000000000")
  # Return plot
  return render_template('index0.html')

@app.route('/3h')
def history3h():
  currentTime = time.time()
  wantedTime = int(time.time() - (3 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index3h.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index3h.html')

@app.route('/6h')
def history6h():
  currentTime = time.time()
  wantedTime = int(time.time() - (6 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index6h.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index6h.html')

@app.route('/12h')
def history12h():
  currentTime = time.time()
  wantedTime = int(time.time() - (12 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index12h.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index12h.html')

@app.route('/24h')
def history24h():
  currentTime = time.time()
  wantedTime = int(time.time() - (24 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index24h.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index24h.html')

@app.route('/3d')
def history3d():
  currentTime = time.time()
  wantedTime = int(time.time() - (3 * 24 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index3d.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index3d.html')

@app.route('/7d')
def history7d():
  currentTime = time.time()
  wantedTime = int(time.time() - (7 * 24 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index7d.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index7d.html')

@app.route('/30d')
def history30d():
  currentTime = time.time()
  wantedTime = int(time.time() - (30 * 24 * 60 * 60))
  # Create plot
  output = executeCommand("python3 plotter.py index30d.html " + str(wantedTime) + " 3000000000")
  # Return plot
  return render_template('index30d.html')


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