import logging
import time
import os
import threading
import re

import subprocess

logger = logging.getLogger(__name__)


class PlaylistGenerator(object):
    def __init__(self, stationName, playlist_path, noise_playlist):

        self.playlist_path = playlist_path
        self.playlist_name = stationName

        self.playlist_noise_entries = noise_playlist
        self.next_noise_index = 0
        self.playlist_event_entries = []
        self.to_remove_event_files = []

        self.playlist_entries = self.playlist_noise_entries[:]

        self.current_file_duration = self.__get_duration()

        self.__incNoiseIndex()

    def __get_duration(self):
        # valid for any audio file accepted by ffprobe
        args = ("ffprobe", "-show_entries", "format=duration", "-i", self.playlist_entries[0])
        popen = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = popen.communicate()
        match = re.search(r"[-+]?\d*\.\d+|\d+", output)
        return float(match.group())

    def __incNoiseIndex(self):
        self.next_noise_index += 1
        if self.next_noise_index > len(self.playlist_noise_entries):
            self.next_noise_index = 0

    def _generate_playlist(self):
        playlist = "{}\n\r{}".format(self._m3u8_header_template(), self._generate_playlist_entries())

        with open(self.playlist_path, 'w+') as m3u8_file:
            m3u8_file.write(playlist)
            m3u8_file.close()
        return playlist

    def _generate_playlist_entries(self):
        playlist = ""
        for entry in self.playlist_entries:
            # playlist += "#EXTINF:{duration},\n\r{media}\n\r".format(duration=float(1), media=(entry))
            playlist += "{media}\n\r".format(media=(entry))

        return playlist  # .replace(" ", "")

    def _generate(self):
        return self._generate_playlist()

    def _m3u8_header_template(self):
        header = "#EXTM3U\n\r".strip()
        return header + "\n\r"

    def getSleepTime(self):
        return self.current_file_duration

    def updateSleepTime(self):
        self.current_file_duration = self.__get_duration()

    def generate(self):
        return self._generate()

    def next(self):
        self.playlist_entries = self.playlist_noise_entries[self.next_noise_index:] + self.playlist_noise_entries[:self.next_noise_index]
        if len(self.playlist_event_entries) > 0:
            self.playlist_entries[0] = self.playlist_event_entries[0]
            self.to_remove_event_files.append(self.playlist_event_entries.pop(0))

        if len(self.to_remove_event_files) > 5:
            file_to_remoev = self.to_remove_event_files.pop(0)
            if os.path.isfile(file_to_remoev):
                os.remove(file_to_remoev)

        self.__incNoiseIndex()

    def addEvent(self, event_path):
        self.playlist_event_entries.append(event_path)

    def stop(self):
        for file_to_remoev in self.to_remove_event_files[:] + self.playlist_event_entries[:]:
            if os.path.isfile(file_to_remoev):
                os.remove(file_to_remoev)


class PlaylistWorking(threading.Thread):
    def __init__(self, stationName, playlist_path,  noise_playlist):
        threading.Thread.__init__(self)
        self._stop_event = threading.Event()
        self.playlist = PlaylistGenerator(stationName,  playlist_path, noise_playlist)

    def stop(self):
        self.playlist.stop()
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def addEvent(self, file_path):
        self.playlist.addEvent(file_path)

    def run(self):
        while not self._stop_event.is_set():
            print_playlist = self.playlist.generate()
            # print(print_playlist)
            self.playlist.next()
            time.sleep(self.playlist.getSleepTime())
            # print(self.playlist.getSleepTime())
            self.playlist.updateSleepTime()
