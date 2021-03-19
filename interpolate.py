#! /usr/bin/python3
import mpld3
from scipy.ndimage.filters import gaussian_filter1d
import matplotlib.pyplot as plt

fig = plt.figure(figsize = (18,8))


datafile = "/Users/eusebiu.rizescu/Data/Git/myprecious/Drafts/dataset-10Mar-10AM.csv"

# Read data
data = open(datafile, "r")
data = data.read().split("\n")[0:-1]

# Sanitize data
dataPoints = []
for element in data:
  if "nan" in element.lower():
    continue
  if len(element.split(",")) > 1:
    dataPoints.append(float(element.split(",")[1]))
  else:
    dataPoints.append(float(element))

dataPoints = dataPoints[0:12]


x = list(range(len(dataPoints)))
y = dataPoints


ysmoothed = gaussian_filter1d(y, sigma=3)
plt.plot(x, y, '-', x, ysmoothed, '--')
#plt.show()


html_str = mpld3.fig_to_html(fig)
Html_file= open("/Users/eusebiu.rizescu/Data/Git/myprecious/Drafts/interpolare.html","w")
Html_file.write(html_str)
Html_file.close()


print(str(y))
print(str(ysmoothed))



