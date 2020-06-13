# 3D Printer CNC Plastic Fuser Experiment

This project holds the code for the 3D printer plastic fuser experiment I did.
Details about it can be found at https://koppanyhorvath.blogspot.com/2020/05/using-3d-printer-as-cnc-plastic-welding.html

## Files

**gcode.py** - The file that contains the code to control the 3D printer to run the test. There are very few comments and it's probably written badly, so tread with care. This is why I tried to make it have a good text based interface, so you wouldn't have to really touch this so long as your setup is similar.

**points.txt** - This file is an example of the 5 point printer calibration file. The 5 points are lower left, upper left, upper right, lower right, and center, in that order with all X, Y, and Z coordinates separated by a space and each group of coordinates separated by a newline.

**debug.gcode** - This was debugging output that the program dumps when the PRODUCTION variable is set to False. This way you can verify the paths are correct in ncviewer.com before you run it on your 3D printer. This also features a path of the total workspace that is not included in the serial output sent to the printer so you can check alignment.

**output.txt** - This is a full copy of what the terminal looked like after the test was done running to show how the calibration routine and program execution looks like. The text is color coded but none of that is shown in this text file.
