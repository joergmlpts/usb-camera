# USB Camera on Linux

This repository provides Python code to connect a microscope, or another USB camera, to Linux and show its video stream, take photos and record videos. It looks like this:

![GUI](/images/gui.png)

## Dependencies

This code has been written in Python3. It relies on OpenCV to connect to the camera and to save pictures and videos. The gui is written in `PyQt5`. Both necessary packages can be installed on Ubuntu Linux with this command:
```
sudo apt install python3-pyqt5 python3-opencv
```

On other platforms `PyQt5` and `opencv` can be installed with this command
```
pip install opencv-python PyQt5
```
where `pip3` should be called instead of `pip` when appropriate to avoid accidentally installing packages for Python 2.

## Command-line

Command-line arguments are supported. Command-line arguments are the cameras to present. They are checked for validity and presented in a drop-down box. When `usb-camera` is called without arguments, it searches for connected cameras and presents them in a drop-down box. The video stream from the first camera is shown initially.

## Acknowledgements 

The icons were obtained from [publicdomainvectors.org](https://publicdomainvectors.org).
