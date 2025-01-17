import platform
import threading
import queue
import time
import sounddevice as sd
import wave
import os
import subprocess
import logging

import numpy as np
import ffmpeg

import P2Pro.util as util

log = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self, path):
        self.WAVE_OUTPUT_FILENAME = path + '.wav'
        self.CHUNK = 1024  # Number of frames per buffer
        self.FORMAT = 'int16'  # SoundDevice uses string format
        self.RATE = 44100

        # Set number of channels based on platform
        if platform.system() == "Darwin":
            self.CHANNELS = 1
        else:
            self.CHANNELS = 2

        # Prepare to write to the .wav file
        self.wf = wave.open(self.WAVE_OUTPUT_FILENAME, 'wb')
        self.wf.setnchannels(self.CHANNELS)
        self.wf.setsampwidth(2)  # 2 bytes for 'int16'
        self.wf.setframerate(self.RATE)

        self.recording = False
        self.thread = None
        self.frames = []  # Buffer for storing the audio data

    def start(self):
        self.recording = True
        # Start the recording thread
        t = threading.Thread(target=self.record)
        t.start()
        self.thread = t

    def stop(self):
        self.recording = False
        self.thread.join()

        # Write all buffered frames to the wave file
        self._write_to_wavefile()

        self.wf.close()

    def record(self):
        # Callback function to handle audio chunks
        def callback(indata, frames, time, status):
            if status:
                print(f"Status: {status}")
            # Append the recorded frames to the buffer
            self.frames.append(indata.copy())

        # Open the input stream with the specified format and channels
        with sd.InputStream(samplerate=self.RATE, channels=self.CHANNELS,
                            dtype=self.FORMAT, blocksize=self.CHUNK, callback=callback):
            while self.recording:
                sd.sleep(100)  # Sleep while the callback processes data

    def _write_to_wavefile(self):
        # Convert the frames to a single NumPy array and write to the wave file
        audio_data = np.concatenate(self.frames, axis=0)
        self.wf.writeframes(audio_data.astype(np.int16).tobytes())


class VideoRecorder:
    def __init__(self, input_queue: queue.Queue, path: str, radiometry: bool = True, audio: bool = True):
        self.rec_running = False
        self.thread: threading.Thread = None

        self.input_queue = input_queue
        self.path = path
        self.with_radiometry = radiometry
        self.with_audio = audio

    def capture_still(self, path: str):
        # R-JPEG?
        pass

    def rec_thread(self):
        while self.input_queue.empty():
            time.sleep(0.01)
            pass

        # TODO: metadata

        frame = self.input_queue.queue[0]  # peek first element in queue
        rgb_resolution = frame['rgb_data'].shape
        therm_resolution = frame['thermal_data'].shape

        proc_rgb: subprocess.Popen = (
            ffmpeg
            .input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{rgb_resolution[1]}x{rgb_resolution[0]}', use_wallclock_as_timestamps='1')
            .output(self.path + '.rgb.mkv', vcodec='libx264', crf='16')
            .overwrite_output()
            .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
        )
        util.PipeLogger(proc_rgb.stdout, log.debug)
        util.PipeLogger(proc_rgb.stderr, log.debug)

        if self.with_radiometry:
            proc_therm: subprocess.Popen = (
                ffmpeg
                .input('pipe:', format='rawvideo', pix_fmt='gray16le', s=f'{therm_resolution[1]}x{therm_resolution[0]}', use_wallclock_as_timestamps='1')
                .output(self.path + '.therm.mkv', vcodec='ffv1')
                .overwrite_output()
                .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
            )
            util.PipeLogger(proc_therm.stdout, log.debug)
            util.PipeLogger(proc_therm.stderr, log.debug)

        if self.with_audio:
            proc_audio = AudioRecorder(self.path)
            proc_audio.start()

        while self.rec_running:
            try:
                frame = self.input_queue.get(True, 0.1)
            except queue.Empty:
                continue

            proc_rgb.stdin.write(frame['rgb_data'].astype(np.uint8).tobytes())
            if self.with_radiometry:
                proc_therm.stdin.write(frame['thermal_data'].astype(np.uint16).tobytes())

        if self.with_audio:
            proc_audio.stop()

        proc_rgb.stdin.close()
        proc_rgb.wait()

        if self.with_radiometry:
            proc_therm.stdin.close()
            proc_therm.wait()

        # merge files
        in_streams = [ffmpeg.input(self.path + '.rgb.mkv')]
        if self.with_radiometry:
            in_streams.append(ffmpeg.input(self.path + '.therm.mkv'))
        if self.with_audio:
            in_streams.append(ffmpeg.input(self.path + '.wav'))

        out = ffmpeg.output(
            *in_streams,
            self.path + '.mkv',
            vcodec='copy',
            acodec='aac',
            map_metadata=-1,
        )
        ret, err = out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        log.debug(ret.decode('utf-8'))
        log.debug(err.decode('utf-8'))

        try:
            os.remove(self.path + '.rgb.mkv')
            if self.with_radiometry:
                os.remove(self.path + '.therm.mkv')
            if self.with_audio:
                os.remove(self.path + '.wav')
        except FileNotFoundError:
            log.warn("Failed to remove one or more temporary recording files")

        log.info(f"Recording finished.")

    def start(self):
        log.info(f"Starting video recording to file {self.path + '.mkv'} ...")
        self.rec_running = True
        self.rec_thread = threading.Thread(target=self.rec_thread)
        self.rec_thread.start()

    def stop(self):
        self.rec_running = False
        log.info(f"Stopping video recording, merging temp files...")
