import threading
import time
import os
import logging

import cv2
import keyboard

import P2Pro.video
import P2Pro.P2Pro_cmd as P2Pro_CMD
import P2Pro.recorder

logging.basicConfig()
logging.getLogger('P2Pro.recorder').setLevel(logging.INFO)
logging.getLogger('P2Pro.P2Pro_cmd').setLevel(logging.INFO)

try:
    print ("Hotkeys:")
    print ("[q] close openCV window, then close program using [ctrl]+[c]")
    print ("[s] do NUC")
    print ("[b] do NUC for background")
    print ("[d] read shutter state")
    print ("[l] set low gain (high temperature mode)")
    print ("[h] set high gain (low temperature mode)")
    cam_cmd = P2Pro_CMD.P2Pro()

    vid = P2Pro.video.Video()
    video_thread = threading.Thread(target=vid.open, args=(cam_cmd, -1, ))
    video_thread.start()

    while not vid.video_running:
        time.sleep(0.01)

    #rec = P2Pro.recorder.VideoRecorder(vid.frame_queue[1], "test")
    #rec.start()

    # print (cam_cmd._dev)
    # cam_cmd._standard_cmd_write(P2Pro_CMD.CmdCode.sys_reset_to_rom)
    # print(cam_cmd._standard_cmd_read(P2Pro_CMD.CmdCode.cur_vtemp, 0, 2))
    # print(cam_cmd._standard_cmd_read(P2Pro_CMD.CmdCode.shutter_vtemp, 0, 2))

    cam_cmd.pseudo_color_set(0, P2Pro_CMD.PseudoColorTypes.PSEUDO_IRON_RED)

    print(cam_cmd.pseudo_color_get())
    # cam_cmd.set_prop_tpd_params(P2Pro_CMD.PropTpdParams.TPD_PROP_GAIN_SEL, 0)
    print(cam_cmd.get_prop_tpd_params(P2Pro_CMD.PropTpdParams.TPD_PROP_GAIN_SEL))
    print(cam_cmd.get_device_info(P2Pro_CMD.DeviceInfoType.DEV_INFO_GET_PN))

    #rec.stop()
    #vid.stop()

    while True:
        img = vid.frame_queue[0].get(True, 2)
        cv2.imshow('frame',img["rgb_data"])
        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            break
        elif key & 0xFF == ord('s'):
            cam_cmd.shutter_actuate()
        elif key & 0xFF == ord('d'):
            shutter, auto_mode = cam_cmd.get_shutter_state()
        elif key & 0xFF == ord('b'):
            cam_cmd.shutter_background()
        elif key & 0xFF == ord('l'):
            cam_cmd.gain_set_low()
        elif key & 0xFF == ord('h'):
            cam_cmd.gain_set_high()
        elif key & 0xFF == ord('m'):
            cam_cmd.shutter_param_set()
        elif key & 0xFF == ord('n'):
            cam_cmd.shutter_params_print()

except KeyboardInterrupt:
    print("Killing...")
    time.sleep(5)
    pass
os._exit(0)
