#!/usr/bin/env python3

import cv2 # install on Ubuntu with 'sudo apt install python3-opencv'

# if missing, install on Ubuntu with 'sudo apt install python3-pyqt5'
from PyQt5.QtCore    import Qt, QDateTime, QSize, QTimer
from PyQt5.QtGui     import QKeySequence, QImage, QPixmap, QIcon
from PyQt5.QtWidgets import (QApplication, QMainWindow, QAction, QWidget,
                             QVBoxLayout, QHBoxLayout, QFrame, QLabel, qApp,
                             QFileDialog, QGroupBox, QPushButton, QComboBox)
import os, queue, sys, threading, time


class MainWindow(QMainWindow):

    WINDOW_NAME  = 'USB-Camera'
    MSG_DURATION = 5000 # show messages for 5 seconds

    def __init__(self, widget, app):
        QMainWindow.__init__(self)
        self.app = app
        self.widget = widget
        self.setWindowTitle(self.WINDOW_NAME)
        self.setCentralWidget(widget)

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.end_window)
        self.file_menu.addAction(exit_action)

        # Status Bar
        self.status = self.statusBar()

    def end_window(self):
        self.widget.end_widget()
        self.close()

    # show text in status message
    def show_message(self, msg):
        self.status.showMessage(msg, self.MSG_DURATION)
        self.app.processEvents()


class CameraPicture(QLabel):

    def __init__(self, camera_widget):
        super().__init__()
        self.camera_widget = camera_widget

    def sizeHint(self):
        return QSize(self.camera_widget.cam_width + 2 * self.frameWidth(),
                     self.camera_widget.cam_height + 2 * self.frameWidth())

    # display frame in GUI, called by update_frame
    def display_frame(self, frame):
        image = QImage(frame, frame.shape[1], frame.shape[0],
                       frame.strides[0], QImage.Format_RGB888)
        size = QSize(self.size().width() - 2 * self.frameWidth(),
                     self.size().height() - 2 * self.frameWidth())
        self.setPixmap(QPixmap.fromImage(image).scaled(size,
                                                       Qt.KeepAspectRatio))


class CameraWidget(QWidget):

    # messages
    NO_CAMERAS_MSG       = 'No cameras found.'
    CANNOT_OPEN_MSG      = 'Cannot open microscope %s.'
    CANNOT_READ_MSG      = 'Cannot get picture from microscope.'
    TAKING_PICTURE       = "Taking picture '%s'."
    CANNOT_WRITE_PICTURE = "Cannot write picture '%s'."
    RECORDING_VIDEO      = "Recording video '%s'."
    CANNOT_WRITE_VIDEO   = "Cannot write video '%s'."
    PICTURE_TAKEN        = 'Picture %s taken.'

    # record button
    RECORD_VIDEO   = 'Record Video'
    RECORD_ICON    = 'rodentia-icons_media-record.svg'
    STOP_RECORDING = 'Stop Recording'
    STOP_ICON      = 'rodentia-icons_media-playback-stop.svg'
    CAMERA_ICON    = 'mono-camera-mount.svg'

    MIN_TIMER_DELAY = 20 # in milliseconds

    # commands sent from main thread to video thread
    VIDEO_OPEN  = 0
    VIDEO_FRAME = 1
    VIDEO_CLOSE = 2
    VIDEO_EXIT  = 3

    def __init__(self):
        QWidget.__init__(self)
        self.main_window = None
        self.cam = None
        self.cam_width = 640
        self.cam_height = 480
        self.cam_fps = 25.0
        self.cameras = {}
        self.combo_cams2camera = {}
        self.cameras_scanned = False
        self.flip = None
        self.timer = None
        self.icon_dir = os.path.join(os.path.dirname(sys.argv[0]), 'icons')

        # create queue of requests by threads for main thread and gui
        self.requests_queue = queue.Queue(5)

        # create queue and thread to record videos
        self.video_queue = queue.Queue(100)
        self.thread_videos = threading.Thread(target=self.thread_write_videos)
        self.thread_videos.start()

        # create queue and thread to take photos
        self.picture_queue = queue.Queue(5)
        self.thread_pictures = threading.Thread(target=self.
                                                thread_write_pictures)
        self.thread_pictures.start()

        self.picture = None  # next filename when taking picture
        self.video = False   # video recording in progress

        #######
        # GUI #
        #######

        # camera videostream

        self.pixmap_view = CameraPicture(self)
        self.pixmap_view.setFrameShape(QFrame.Box)
        self.pixmap_view.setBaseSize(640, 480)

        # save photos and videos

        self.layout_save = QHBoxLayout()
        self.btn_directory = QPushButton("Output Directory")
        self.btn_directory.clicked.connect(self.change_output_directory)
        self.layout_save.addWidget(self.btn_directory)
        self.label_directory = QLabel('')
        self.layout_save.addWidget(self.label_directory, stretch=1)
        self.set_output_directory(os.getcwd())
        self.btn_take_photo = QPushButton("Take Photo")
        self.btn_take_photo.setIcon(QIcon(os.path.join(self.icon_dir,
                                                       self.CAMERA_ICON)))
        self.btn_take_photo.clicked.connect(self.take_picture)
        self.btn_record_video = QPushButton(self.RECORD_VIDEO)
        self.btn_record_video.setIcon(QIcon(os.path.join(self.icon_dir,
                                                         self.RECORD_ICON)))
        self.btn_record_video.clicked.connect(self.record_video)
        self.layout_save.addWidget(self.btn_take_photo)
        self.layout_save.addWidget(self.btn_record_video)

        # select camera

        self.layout_group_cam = QHBoxLayout()
        self.btn_update_cameras = QPushButton('Re-Scan Cameras')
        self.btn_update_cameras.clicked.connect(self.update_cameras)
        self.combo_cams = QComboBox()
        self.combo_cams.currentIndexChanged.connect(self.change_camera)
        self.combo_flip = QComboBox()
        self.combo_flip.currentIndexChanged.connect(self.change_flip)
        for item in ['No Flip', 'Flip Horizontally', 'Flip Vertically',
                     'Flip Both']: self.combo_flip.addItem(item)
        self.layout_group_cam.addWidget(QLabel('Camera:'))
        self.layout_group_cam.addWidget(self.combo_cams)
        self.layout_group_cam.addWidget(self.combo_flip)
        self.layout_group_cam.addWidget(self.btn_update_cameras)

        # main layout

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.layout_group_cam)
        self.main_layout.addWidget(self.pixmap_view)
        self.main_layout.addLayout(self.layout_save)
        self.setLayout(self.main_layout)

        self.enable_buttons(False)

    # called upon exit, stops timer and shuts down threads
    def end_widget(self):
        self.end_camera()
        self.picture_queue.put(None)
        self.video_queue.put((self.VIDEO_EXIT, None))
        self.thread_pictures.join()
        self.thread_videos.join()

    # show status message
    def show_message(self, msg):
        if self.main_window:
            self.main_window.show_message(msg)

    # clear status message
    def clear_message(self):
        self.show_message('')

    # enable or disable buttons, only enabled when a camera selected
    def enable_buttons(self, enable=True):
        for btn in [self.btn_take_photo, self.btn_record_video,
                    self.combo_flip]: btn.setEnabled(enable)

    # display file dialog to select an output directory
    def change_output_directory(self):
        directory = QFileDialog.getExistingDirectory(None,
                         "choose output directory", self.output_path,
                         QFileDialog.ShowDirsOnly)
        if directory:
            self.set_output_directory(directory)
            self.clear_message()
        else:
            self.show_message('Output directory not changed.')

    # set output directory
    def set_output_directory(self, directory):
        self.output_path = directory
        self.label_directory.setText(directory)

    # test if camera can be opened
    def camera_exists(self, idx):
        cam = cv2.VideoCapture(idx)
        rsl = False
        if cam.isOpened():
            self.cameras[idx] = ('%dx%d %.1ffps' %
                                 (cam.get(cv2.CAP_PROP_FRAME_WIDTH),
                                  cam.get(cv2.CAP_PROP_FRAME_HEIGHT),
                                  cam.get(cv2.CAP_PROP_FPS)))
            rsl = True
        cam.release()
        return rsl

    # query available cameras, populate combo box
    def update_cameras(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.end_camera()
        self.cameras = {}
        if not self.cameras_scanned and len(sys.argv) > 1:
            for arg in sys.argv[1:]:
                if arg.isdigit():
                    arg = int(arg)
                self.camera_exists(arg)
        else:
            idx = 0
            no_failures = 0
            MAX_FAILURES = 2
            while True:
                if self.camera_exists(idx):
                    no_failures = 0
                else:
                    no_failures += 1
                if no_failures > MAX_FAILURES:
                    break
                idx += 1
        self.cameras_scanned = True
        self.combo_cams.clear()
        self.combo_cams2camera = {}
        for idx, info in self.cameras.items():
            item = f'{idx}: {info}'
            self.combo_cams2camera[item] = idx
            self.combo_cams.addItem(item)
        QApplication.restoreOverrideCursor()

    # called upon selection of another camera
    def change_camera(self, i):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.end_camera()
        if i >= 0:
            self.begin_camera(self.combo_cams2camera[self.combo_cams.
                                                     itemText(i)])
        QApplication.restoreOverrideCursor()

    # called upon selection of another flip
    def change_flip(self, i):
        idx2flip = [None, 1, 0, -1]
        self.flip = idx2flip[i]

    # initialize GUI, query available cameras, select first camera
    def initialize(self, main_window):
        self.main_window = main_window
        self.update_cameras()
        if not self.cameras:
            self.show_message(self.NO_CAMERAS_MSG)
            return
        self.begin_camera(self.combo_cams2camera[self.combo_cams.
                                                 currentText()])

    # open camera and set up timer to process frames
    def begin_camera(self, camera):
        self.clear_message()
        assert camera in self.cameras
        self.cam = cv2.VideoCapture(camera)
        if not self.cam.isOpened():
            no_retries = 0
            MAX_RETRIES = 5
            while not self.cam.isOpened() and no_retries < MAX_RETRIES:
                time.sleep(1)
                self.cam.open(camera)
                no_retries += 1
            if not self.cam.isOpened():
                self.end_camera()
                self.show_message(self.CANNOT_OPEN_MSG % camera)
                return
        self.cam_width = int(self.cam.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cam_height = int(self.cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cam_fps = self.cam.get(cv2.CAP_PROP_FPS)
        self.pixmap_view.setMinimumSize(self.cam_width // 2,
                                        self.cam_height // 2)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer_delay = int(1000.0 / self.cam_fps)
        while self.timer_delay < self.MIN_TIMER_DELAY:
            self.timer_delay = self.MIN_TIMER_DELAY
        self.timer.start(self.timer_delay)
        self.enable_buttons()

    # end camera use
    def end_camera(self):
        self.enable_buttons(False)
        if self.cam:
            self.cam.release()
            self.cam = None
        if self.timer:
            self.timer.stop()
            self.timer = None
        self.end_video()

    # read one frame from camera, called by update_frame
    def read_frame(self):
        if self.cam:
            ret_val, bgr_frame = self.cam.read()
            if ret_val:
                if self.flip is not None:
                    bgr_frame = cv2.flip(bgr_frame, self.flip)
                return bgr_frame, cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            else:
                self.show_message(self.CANNOT_READ_MSG)
                self.cam = None
                self.timer.stop()

    # for my 25fps microscope, the timer calls this function every 40ms
    def update_frame(self):
        while not self.requests_queue.empty():
            req = self.requests_queue.get()
            req()
            self.requests_queue.task_done()
        frames = self.read_frame()
        if frames is not None:
            bgr_frame, rgb_frame = frames
            if self.picture:
                self.picture_queue.put((self.picture, bgr_frame))
                self.picture = None
            if self.video:
                self.video_queue.put((self.VIDEO_FRAME, bgr_frame))
            self.pixmap_view.display_frame(rgb_frame)

    # generate a filename that consists in the current date and time
    def generate_filename(self):
        format = 'yyyy-MM-dd_HH-mm-ss'
        return os.path.join(self.output_path,
                            QDateTime.currentDateTime().toString(format))

    # makes sure that 'msg' disappears from scope and cannot be re-used
    def queue_message(self, msg_base, filename):
        msg = msg_base % filename
        self.requests_queue.put(lambda : self.show_message(msg))

    # runs in thread, gets filenames and frames and writes pictures
    def thread_write_pictures(self):
        while True:
            cmd = self.picture_queue.get()
            if not cmd is None:
                filename, frame = cmd
                self.queue_message(self.TAKING_PICTURE if cv2.imwrite(filename,
                                                                      frame)
                                   else self.CANNOT_WRITE_PICTURE, filename)
            self.picture_queue.task_done()
            if cmd is None:
                break

    # runs in thread, writes videos
    def thread_write_videos(self):
        video = None
        while True:
            cmd, arg = self.video_queue.get()
            if cmd == self.VIDEO_FRAME:
                if video:
                    video.write(arg)
            elif cmd == self.VIDEO_OPEN:
                fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
                video = cv2.VideoWriter(arg, fourcc,
                                        1000.0 / self.timer_delay,
                                        (self.cam_width, self.cam_height))
                if video and video.isOpened():
                    self.queue_message(self.RECORDING_VIDEO, arg)
                    self.requests_queue.put(lambda:self.btn_record_video.\
                                            setIcon(QIcon(os.path.join(self.\
                                                                       icon_dir,
                                                              self.STOP_ICON))))
                    self.requests_queue.put(lambda:self.btn_record_video.\
                                            setText(self.STOP_RECORDING))
                else:
                    video = None
                    self.queue_message(self.CANNOT_WRITE_VIDEO, arg)
                    self.video = False
            elif cmd == self.VIDEO_CLOSE:
                if video:
                    video.release()
                    video = None
            self.video_queue.task_done()
            if cmd == self.VIDEO_EXIT:
                if video:
                    video.release()
                    video = None
                break

    # request to take a picture in next call of update_frame
    def take_picture(self):
        self.picture = self.generate_filename() + '.jpg'

    # request to record a video of subsequent calls of update_frame
    def record_video(self):
        if self.video:
            self.end_video()
            return
        filename = self.generate_filename() + '.mp4'
        # send open command and filename to thread
        self.video_queue.put((self.VIDEO_OPEN, filename))
        self.video = True

    # end video recording
    def end_video(self):
        if self.video:
            self.btn_record_video.setText(self.RECORD_VIDEO)
            self.btn_record_video.setIcon(QIcon(os.path.join(self.icon_dir,
                                                             self.RECORD_ICON)))
            # send close command to thread
            self.video_queue.put((self.VIDEO_CLOSE, None))
            self.clear_message()
            self.video = False


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = CameraWidget()
    app.aboutToQuit.connect(widget.end_widget)
    main_window = MainWindow(widget, app)
    widget.initialize(main_window)
    main_window.show()
    sys.exit(app.exec_())
