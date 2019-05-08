from datetime import datetime
from fnmatch import fnmatch
import os
# # pip install wavio --user
import wavio

# pip install PySoundFile --user
# import soundfile as sf

import numpy as np

# import matplotlib.pyplot as plt


class SoundGenerator():
    def __init__(self, rate=44100, fre=440, seconds_split=1, sps=10, noise_dbfs=12):
        self.rate = int(rate)
        self.fre = int(fre)

        self.noise_dbfs = int(noise_dbfs)

        # self.noise_mu = int(0)
        self.noise_sigma = int(1)

        self.seconds_split = int(seconds_split)
        self.samples_per_second = int(sps)

        self.min_scale = 1
        self.max_scale = self.noise_dbfs * 5

        self.file_ext = '.wav'

    def __note(self, len, amp):
        if amp < self.noise_dbfs:
            amp = 0

        t = np.linspace(0, len, len * self.rate)
        data = np.sin(2 * np.pi * self.fre * t) * amp
        return data
        # return data.astype(np.int16)

    def __generateNoise(self, time, amp):
        # noise_mu = self.noise_mu
        noise_sig = self.noise_sigma

        if amp < self.noise_dbfs:
            noise_sig = self.noise_dbfs * 0.2

        return np.random.uniform(-1 * noise_sig, 1 * noise_sig, int(self.rate * time))
        # return np.random.uniform(-1,0, int(self.rate * time))
        # return np.random.normal(noise_mu, noise_sig, int(self.rate * time))

    def __generateSound(self, _t, _s_n):

        # median = np.mean(_s_n)
        _sound = np.array([])
        for i, n in enumerate(_t):
            if i == 0:
                continue
            else:
                seconds = n - _t[i - 1]

                _note = np.array(self.__note(seconds, _s_n[i - 1])) + self.__generateNoise(seconds, _s_n[i - 1])
                _sound = np.append(_sound, _note)

        return _sound

    def __scale_to_sampwidth(self, data, sampwidth, vmin, vmax):
        # Scale and translate the values to fit the range of the data type
        # associated with the given sampwidth.
        _sampwidth_dtypes = {1: np.uint8,
                             2: np.int16,
                             3: np.int32,
                             4: np.int32}
        _sampwidth_ranges = {1: (0, 256),
                             2: (-2**15, 2**15),
                             3: (-2**23, 2**23),
                             4: (-2**31, 2**31)}

        data = data.clip(vmin, vmax)

        dt = _sampwidth_dtypes[sampwidth]
        if vmax == vmin:
            data = np.zeros(data.shape, dtype=dt)
        else:
            outmin, outmax = _sampwidth_ranges[sampwidth]
            if outmin != vmin or outmax != vmax:
                vmin = float(vmin)
                vmax = float(vmax)
                data = (float(outmax - outmin) * (data - vmin)
                        / (vmax - vmin)).astype(np.int64) + outmin
                data[data == outmax] = outmax - 1
            data = data.astype(dt)

        return data

    def __generateFile(self, path, sound):
        # plt.title(os.path.basename(path))
        # plt.plot(np.linspace(0, 1, len(sound)), sound)
        # plt.grid(True)
        # plt.xlabel('Seconds')
        # plt.ylabel('Amplitude [dB]')
        # plt.show()

        wavio.write(path, sound, self.rate, sampwidth=1, scale=(self.min_scale, self.max_scale))
        # sf.write(path, self.__scale_to_sampwidth(sound, 2, self.min_scale, self.max_scale), self.rate)

    def generate(self, t, s_n, folder_path):
        files = []

        _from = 0
        _to = 0
        for i in range(len(t)):
            _to = i
            if t[_to] - t[_from] >= self.seconds_split:
                # print(_from, _to, _to - _from, t[_to] - t[_from], t[_from], t[_to])
                wav_path = os.path.join(folder_path, str(t[_from]) + "_" + str(t[_to]) + self.file_ext)
                try:
                    self.__generateFile(wav_path, self.__generateSound(np.array(t[_from:_to]), np.array(s_n[_from:_to])))
                    files.append(wav_path)
                except Exception as e:
                    print(e)
                    pass

                _from = _to

        while t[_to] - t[_from] < self.seconds_split:
            # print(_to, t[_to], (self.seconds_split / self.samples_per_second))
            t.append(t[_to] + (self.seconds_split / float(self.samples_per_second)))
            s_n.append(0)
            _to = len(t) - 1

        wav_path = os.path.join(folder_path, str(t[_from]) + "_" + str(t[_to]) + self.file_ext)
        try:
            sound = self.__generateSound(np.array(t[_from:_to]), np.array(s_n[_from:_to]))
            self.__generateFile(wav_path, sound)
            files.append(wav_path)
        except Exception as e:
            print(e)
            pass

        return files
