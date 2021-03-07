from flask import Flask, render_template
from plotter import mainFunction
import subprocess # for executing bash commands

##### Variables #####
app = Flask(__name__)

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

@app.route('/')
def index():
    # Create plot
    output = executeCommand("python3 plotter.py")
    # Return plot
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')