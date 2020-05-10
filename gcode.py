import serial
import time
import traceback
import sys
import math

PRODUCTION = True

if PRODUCTION:
	serial.Serial("/dev/ttyUSB0", 9600)
	ser = serial.Serial("/dev/ttyUSB0", 115200)
else:
	f = open("debug.gcode", "w")
	f.write("")
	f.close()

def red():
	sys.stdout.write("\x1b[31m")
def green():
	sys.stdout.write("\x1b[32m")
def yellow():
	sys.stdout.write("\x1b[33m")
def reset():
	sys.stdout.write("\x1b[0m")
def printRed(s):
	red(); print s; reset()
def printGreen(s):
	green(); print s; reset()
def printYellow(s):
	yellow(); print s; reset()

def sendCommand(c, d=0.1):
	printGreen(c)
	if not PRODUCTION:
		f = open("debug.gcode", "a+")
		f.write(c + '\n')
		f.close()
		print "ok"
		return "ok"
	ser.reset_input_buffer()
	ser.write(c + '\n')
	ser.flush()
	time.sleep(d)
	out = ser.readline()
	while not out.lower().startswith("ok"):
		print out.strip()
		out = ser.readline()
	#out = ser.read(1) + ser.read(ser.in_waiting)
	#if not out.lower().startswith("ok"):
	#	raise Exception("Printer response does not start with 'ok': " + out)
	print out.strip()
	return out

def clip(i):
	return "{:.1f}".format(i)

def move(x=None, y=None, z=None, s=None):
	if x == None and y == None and z == None and s == None:
		raise Exception("Function 'move' requires at least one input")
	c = "G0"
	if s != None: c += " F" + clip(s)
	if x != None: c += " X" + clip(x)
	if y != None: c += " Y" + clip(y)
	if z != None: c += " Z" + clip(z)
	return sendCommand(c, 0.01)

################ Printer calibration section ###################

def getCorner(gx=0.0, gy=0.0):
	while 1:
		nx = raw_input("X (" + clip(gx) + "): ")
		if nx == "#":
			break
		elif nx != "":
			gx = float(nx)
		ny = raw_input("Y (" + clip(gy) + "): ")
		if ny == "#":
			break
		elif ny != "":
			gy = float(ny)
		move(gx, gy)
	return (gx, gy)

def inputCorners():
	yellow()
	print "Enter a value for X or Y"
	print "Leave empty to reuse it"
	print "Enter # to signal done with this corner"
	corns = [(0.0, 0.0)]
	for c in ["lower left", "upper left", "upper right", "lower right"]:
		printGreen("Specify " + c + " corner")
		corns.append(getCorner(corns[-1][0], corns[-1][1]))
	corns.pop(0)
	return corns

def getHeight(mx=0.0, my=0.0):
	move(z=10)
	move(mx, my)
	gz = 10.0
	while 1:
		nz = raw_input("Z (" + clip(gz) + "): ")
		if nz == "#":
			break
		elif nz != "":
			gz = float(nz)
		move(z=gz)
	return gz

def inputHeights(corns):
	yellow()
	print "Enter a height for the following points"
	print "Enter # to signal done with this point"
	heights = []
	for c in corns:
		printGreen("Specify (" + clip(c[0]) + "," + clip(c[1]) + ") height")
		heights.append(getHeight(c[0], c[1]))
	return heights

def getPoints():
	points = []
	choice = raw_input("Load calibration data from file? (Y/n) ").lower()
	if choice == 'y' or choice == '':
		f = open(raw_input("File name: "), "r")
		for _ in xrange(5):
			l = f.readline().strip().split()
			if len(l) < 3:
				raise Exception("Data file format incorrect")
			points.append(tuple(map(float, l)))
		f.close()
	else:
		corners = inputCorners()
		corners.append(( #[lower left, upper left, upper right, lower right, center]
			(corners[0][0] + corners[1][0] + corners[2][0] + corners[3][0]) / 4.0,
			(corners[0][1] + corners[1][1] + corners[2][1] + corners[3][1]) / 4.0))
		heights = inputHeights(corners) #[lower left, upper left, upper right, lower right, center]
		points = [(corners[i][0], corners[i][1], heights[i]) for i in xrange(5)]
		choice = raw_input("Save calibration data to file? (Y/n) ").lower()
		if choice == 'y' or choice == '':
			f = open(raw_input("File name: "), "w")
			for p in points:
				f.write("{} {} {}\n".format(*p))
			f.close()
	return points

################ Warped bed compensation section ###################

def lineInterp(start, end, prog):
	#returns point on line between start and end coord by percentage
	return (
		1.0 * (end[0] - start[0]) * prog + start[0],
		1.0 * (end[1] - start[1]) * prog + start[1])

def findAngle(ptOne, ptTwo, ptThree):
	a = math.atan2(ptTwo[1] - ptOne[1], ptTwo[0] - ptOne[0])
	a -= math.atan2(ptThree[1] - ptOne[1], ptThree[0] - ptOne[0])
	if a < 0: a = 2 * math.pi - a
	return a % (2 * math.pi)

def findTri(pts, pt):
	tris = [
		(pts[4], pts[0], pts[1]),
		(pts[4], pts[1], pts[2]),
		(pts[4], pts[2], pts[3]),
		(pts[4], pts[3], pts[0])]
	minA = None
	minT = None
	for t in tris:
		a1 = findAngle(pt, t[0], t[1])
		a2 = findAngle(pt, t[1], t[2])
		a3 = findAngle(pt, t[2], t[0])
		a = abs((a1 + a2 + a3) - (2 * math.pi))
		if minA == None or a < minA:
			minA = a
			minT = t
	#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! there's a problem with this function !!!!!!!!!!!!!!!!!!!!!!!!!!!
	return minT
	if abs(2 * math.pi - minA) <= 0.01:
		return minT
	return None

def addHeight(pts, pt):
	for p in pts: #if the x,y exists in one of the pts, return that
		if p[0] == pt[0] and p[1] == pt[1]:
			return (pt[0], pt[1], p[2])
	tri = findTri(pts, pt) #else find tri and calculate it
	if tri == None:
		raise Exception("Point {} is out of bounds".format(pt))
	#calculates intersection of line(middle, point) and line(leg1, leg2)
	#finds height at that intersection
	#then calculates height of point between line(intersection, middle)
	h = pt[0] - tri[0][0]
	i = tri[0][0]
	j = pt[1] - tri[0][1]
	k = tri[0][1]
	l = tri[2][0] - tri[1][0]
	m = tri[1][0]
	n = tri[2][1] - tri[1][1]
	o = tri[1][1]
	b = (h*o - h*k - j*m + j*i)/(j*l - h*n)
	x = l*b + m
	y = n*b + o
	majd = math.sqrt((tri[2][0] - tri[1][0])**2 + (tri[2][1] - tri[1][1])**2)
	mind = math.sqrt((x - tri[1][0])**2 + (y - tri[1][1])**2)
	c = mind / majd
	z1 = (tri[2][2] - tri[1][2])*c + tri[1][2]
	majd = math.sqrt((x - tri[0][0])**2 + (y - tri[0][1])**2)
	mind = math.sqrt((pt[0] - tri[0][0])**2 + (pt[1] - tri[0][1])**2)
	c = mind / majd
	z2 = (z1 - tri[0][2])*c + tri[0][2]
	return (pt[0], pt[1], z2)

######################

def genLine(pts, xp, yps, ype):
	topStart = pts[1]
	topEnd = pts[2]
	bottomStart = pts[0]
	bottomEnd = pts[3]
	topPt = lineInterp(topStart, topEnd, xp)
	bottomPt = lineInterp(bottomStart, bottomEnd, xp)
	startPt = lineInterp(bottomPt, topPt, yps)
	endPt = lineInterp(bottomPt, topPt, ype)
	return (addHeight(pts, startPt), addHeight(pts, endPt))

def genCode(pts):
	for gj in xrange(3):
		for gi in xrange(3):
			temp = 5 * (gj * 3 + gi) + 145
			start = (
				gi/3.0 + 1.5/76,
				gj/3.0 + 1.0/36)
			move(z=20, s=3000)
			sendCommand("M400")
			printYellow("Heating up to {}C".format(temp))
			sendCommand("M109 R{}".format(temp))
			for gk in xrange(12):
				speed = -954 * gk + 11994 #start fast end slow
				ln = genLine(pts, start[0] + gk * 1.0/38, start[1], start[1] + 5.0/18)
				move(ln[0][0], ln[0][1], s=3000) #hover on target
				move(z=ln[0][2], s=speed) #touch down
				move(ln[1][0], ln[1][1], ln[1][2]) #fuse the plastic
				move(z=20) #lift off
	sendCommand("M400")
	sendCommand("M104 S0")

# 9 squares, starting at 145C, increment 5C
# 12 lines, starting at 11994mm/min, decrement 954mm/min

#######################

try:
	
	printYellow("Waiting for printer boot")
	if PRODUCTION:
		ser.reset_input_buffer()
		o = ser.read(1)
		time.sleep(5)
		o += ser.read(ser.in_waiting)
		print o
	
	printYellow("Setting coordinate system to absolute")
	sendCommand("G90")
	printYellow("Homing the printer")
	sendCommand("G0 Z10") #needed to prevent clashing with frame if stopped when touching
	sendCommand("G28")
	
	move(z=10, s=12000)
	
	points = getPoints()
	
	genCode(points)
	
	if not PRODUCTION: #draw working surface
		for p in points:
			move(p[0], p[1], p[2])
		move(0, 0, 0)
	
except BaseException as err:
	red(); print "ERROR"
	traceback.print_exc()
finally:
	printYellow("Closing connection")
	if PRODUCTION:
		ser.close()

reset()
