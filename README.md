# USB Camera on Linux

This repository provides Python code to connect a microscope, or other USB camera, to Linux and display its video stream, take photos and record videos. It looks like this:

![GUI](/images/gui.png)

## Dependencies

This code has been written in Python3. It relies on OpenCV to connect to the camera and to save pictures and videos. The GUI is written in `PyQt5`. Both necessary packages can be installed with this command on Ubuntu Linux:
```
sudo apt install python3-pyqt5 python3-opencv
```

On other platforms `PyQt5` and `opencv` can be installed with this command
```
pip install opencv-python PyQt5
```
where `pip3` should be used instead of `pip` when appropriate to avoid accidentally installing Python 2 packages.

## Command-line

Command-line arguments are supported. Command-line arguments are the cameras to display. They are validated and presented in a drop-down box. When `usb-camera` is called without arguments, it searches for connected cameras and presents them in a drop-down box. The video stream from the first camera is displayed first.

## Acknowledgements 

Icons are obtained from [publicdomainvectors.org](https://publicdomainvectors.org).
