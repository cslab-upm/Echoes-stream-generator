# Echoes-stream-generator
Contadores de Estrellas - Server Side - Echoes generator


Requirements:
    [Liquidsoap](https://www.liquidsoap.info/)
    Ffmpeg
    psutil, configparser, paho-mqtt, wavio

```
   sudo apt install opam
   opam init
   eval `opam config env`
   opam install depext
   opam depext taglib mad lame vorbis cry ssl samplerate magic opus liquidsoap
   opam install taglib mad lame vorbis cry ssl samplerate magic opus liquidsoap

   sudo apt install ffmpeg
   
   pip install psutil --user
   pip install configparser --user
   pip install paho-mqtt --user
   pip install wavio --user
```

Create config.py file with:
```
[ICECAST]
host =
port =
source_pass =

[MQTT]
host =
port =

[LIQUIDSOAP]
path =
```

Execute in background:

`nohup /usr/bin/python generator.py </dev/null >/dev/null 2>&1 & # completely detached from terminal`
