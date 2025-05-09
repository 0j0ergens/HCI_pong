"""
    # PONG PLAYER EXAMPLE

    HOW TO CONNECT TO HOST AS PLAYER 1
    > python pong-audio-player.py p1 --host_ip HOST_IP --host_port 5005 --player_ip YOUR_IP --player_port 5007

    HOW TO CONNECT TO HOST AS PLAYER 2
    > python pong-audio-player.py p2 --host_ip HOST_IP --host_port 5006 --player_ip YOUR_IP --player_port 5008

    about IP and ports: 127.0.0.1 means your own computer, change it to play across computer under the same network. port numbers are picked to avoid conflits.

    DEBUGGING:
    
    You can use keyboards to send command, such as "g 1" to start the game, see the end of this file


        source pong/bin/activate

    start host game: 
        python pong-audio-host-do-not-edit.py
    open second player: 
        python pong-audio-player.py p1
    open third player: 
        python pong-audio-player.py p2

    
        #aubio sources: https://github.com/aubio/aubio/blob/master/python/demos/demo_pyaudio.py



"""
#native imports
import time
from playsound import playsound
import argparse
import pyttsx3



from pysinewave import SineWave
from pythonosc import osc_server
from pythonosc import dispatcher
from pythonosc import udp_client
import subprocess

# threading so that listenting to speech would not block the whole program
import threading
# speech recognition (default using google, requiring internet)
import speech_recognition as sr
# pitch & volume detection
import aubio
import numpy as num
import pyaudio
import wave

#pitch output
# -------------------------------------#
# start a thread to determine + output pitch of ball movement
audio_lock = threading.Lock()
is_audio_playing = False
prev_pitch = None
pitch_disabled = False 
# -------------------------------------#

voice_allowed = True 


# Initialize sine wave globally
sinewave = SineWave(pitch=0, pitch_per_second=5)


last_pitch_p1 = None
last_pitch_p2 = None
paddle_pos1 = 225  # Start in the middle of the board
paddle_pos2 = 225
stop_pitch = False
prev_pitch = None
p1_in = False
p2_in = False
prev_x = None 
big_paddle = False
frozen = False

mode = ''
debug = False
quit = False


host_ip = "127.0.0.1"
host_port_1 = 5005 # you are player 1 if you talk to this port
host_port_2 = 5006
player_1_ip = "127.0.0.1"
player_2_ip = "127.0.0.1"
player_1_port = 5007
player_2_port = 5008

player_ip = "127.0.0.1"
player_port = 0
host_port = 0

started = False

turn = 1



if __name__ == '__main__' :

    parser = argparse.ArgumentParser(description='Program description')
    parser.add_argument('mode', help='host, player (ip & port required)')
    parser.add_argument('--host_ip', type=str, required=False)
    parser.add_argument('--host_port', type=int, required=False)
    parser.add_argument('--player_ip', type=str, required=False)
    parser.add_argument('--player_port', type=int, required=False)
    parser.add_argument('--debug', action='store_true', help='show debug info')
    args = parser.parse_args()
    print("> run as " + args.mode)
  
    mode = args.mode
   

    if (args.host_ip):
        host_ip = args.host_ip
    if (args.host_port):
        host_port = args.host_port
    if (args.player_ip):
        player_ip = args.player_ip
    if (args.player_port):
        player_port = args.player_port
    if (args.debug):
        debug = True

# GAME INFO

# functions receiving messages from host
# TODO: add audio output so you know what's going on in the game

def output_pitch_thread(pitch_num):
    global is_audio_playing, sinewave, stop_pitch

    if pitch_num == None or stop_pitch: 
        return 

    with audio_lock:
        if is_audio_playing:
            return
        is_audio_playing = True
    sinewave.set_volume(1)
    try:
        #print(f"Playing pitch: {pitch_num}")
        sinewave.set_pitch(pitch_num)
        sinewave.play()
        time.sleep(.2)  
    finally:
        with audio_lock:
            is_audio_playing = False

def output_message(message): 
    engine.say(message)
    engine.runAndWait()

def on_receive_game(address, *args):
    global started 
    print("> game state: " + str(args[0]))
    if int(args[0]) == 1:  
        started = True
        print("Game started")
    else:
        started = False
        print("Game not started")

def on_receive_ball(address, *args):
    global prev_pitch, pitch_disabled, prev_x 

    correct_direction = True 
    x_pos = float(args[0])
    if prev_x is not None:
        if mode == 'p1':  
            if x_pos > prev_x: 
                correct_direction = False 
        elif mode == 'p2': 
            if x_pos < prev_x: 
                correct_direction = False
    prev_x = x_pos 

    y_pos = float(args[1]) 
    pitch = 12 - int(y_pos // 37.5) 

    if not pitch_disabled and correct_direction: 
        if pitch != prev_pitch: 
            prev_pitch = pitch
            threading.Thread(target=output_pitch_thread, args=(pitch,)).start()
    elif not correct_direction:  
        with audio_lock:
            sinewave.stop() 

def on_receive_paddle(address, *args):
    # print("> paddle position: (" + str(args[0]) + ", " + str(args[1]) + ")")
    pass

def on_receive_hitpaddle(address, *args):
    # example sound
    hit(3)
    print("> ball hit at paddle " + str(args[0]) )

def on_receive_ballout(address, *args):
    print("> ball went out on left/right side: " + str(args[0]) )
    hit(2)
    side = args[0]
    if (mode == 'p1' and side == 2) or (mode == 'p2' and side == 1): 
        ps('sounds/win.wav')
    if (mode == 'p1' and side == 1) or (mode == 'p2' and side == 2): 
        ps('sounds/hit.wav')
   
    global pitch_disabled 
    pitch_disabled = True 
    time.sleep(.5)
    pitch_disabled = False 


def on_receive_ballbounce(address, *args):
    global pitch_disabled
    # example sound
    hit(1)
   # pitch_disabled = False
    print("> ball bounced on up/down side: " + str(args[0]) )

def on_receive_scores(address, *args):
    global s1, s2
    s1 = str(args[0])
    s2 = str(args[2])
    score = f'say p1 {s1} to p2 {s2}'
    subprocess.run(score, shell=True)
   # output_message(s1 + " to " + s2)
    print("> scores now: " + str(args[0]) + " vs. " + str(args[1]))

def on_receive_level(address, *args):
    print("> level now: " + str(args[0]))


cur_powerup = None
def on_receive_powerup(address, *args):
    
    global big_paddle, frozen, cur_powerup
    cur_powerup = args[0]
    print("> powerup now: " + str(args[0]))
    pu = args[0]
    print(pu)
    if cur_powerup == 0 and frozen: 
        frozen = False
        ps("sounds/unfrozen.mp3")

    if mode == 'p1': 
        
        print("ACCESED")
        if pu == 1: 
            frozen = True
            ps("sounds/frozen.mp3")
        if pu == 3: 
            print("bpaddle")
            big_paddle = True
            ps("sounds/bp.mp3")
    
    if mode == 'p2': 
        print("2ACCESED")
        if pu == 2: 
            frozen = True 
            ps("sounds/frozen.mp3")
        if pu == 4: 
            ps("sounds/bp.mp3")

    else: 
        big_paddle = False
    # 1 - freeze p1
    # 2 - freeze p2
    # 3 - adds a big paddle to p1, not use
    # 4 - adds a big paddle to p2, not use

def on_receive_p1_bigpaddle(address, *args):
    global big_paddle
    print("> p1 has a big paddle now")
    ps("sounds/activated.mp3")
    # when p1 activates their big paddle

def on_receive_p2_bigpaddle(address, *args):
    global big_paddle
    print("> p2 has a big paddle now")
    ps("sounds/activated.mp3")
    # when p2 activates their big paddle

def on_receive_hi(address, *args):
    global p1_in, p2_in 
    if mode == 'p1':
        p1_in = True 
    
    if mode == 'p2':
        p2_in == True 
    
    if not p1_in or not p2_in: 
        p1_in = True 
        p2_in = True 
        if started == False: 
            ps("sounds/Intro.mp3")
            print("Game not started")
        client.send_message("/hi", player_ip)
    
    if p1_in and p2_in: 
        ps("sounds/hi.mp3")

    print("> opponent says hi!")


dispatcher_player = dispatcher.Dispatcher()
dispatcher_player.map("/hi", on_receive_hi)
dispatcher_player.map("/game", on_receive_game)
dispatcher_player.map("/ball", on_receive_ball)
dispatcher_player.map("/paddle", on_receive_paddle)
dispatcher_player.map("/ballout", on_receive_ballout)
dispatcher_player.map("/ballbounce", on_receive_ballbounce)
dispatcher_player.map("/hitpaddle", on_receive_hitpaddle)
dispatcher_player.map("/scores", on_receive_scores)
dispatcher_player.map("/level", on_receive_level)
dispatcher_player.map("/powerup", on_receive_powerup)
dispatcher_player.map("/p1bigpaddle", on_receive_p1_bigpaddle)
dispatcher_player.map("/p2bigpaddle", on_receive_p2_bigpaddle)
# -------------------------------------#

# CONTROL

# TODO add your audio control so you can play the game eyes free and hands free! add function like "client.send_message()" to control the host game
# We provided two examples to use audio input, but you don't have to use these. You are welcome to use any other library/program, as long as it respects the OSC protocol from our host (which you cannot change)

# example 1: speech recognition functions using google api
# -------------------------------------#

engine = pyttsx3.init()

def listen_to_speech():
    global quit, started, pitch_disabled, cur_powerup, stop_pitch
    while not quit:
    
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("[speech recognition] Say something!")
            audio = r.listen(source)
        # recognize speech using Google Speech Recognition
        try:
            # for testing purposes, we're just using the default API key
            # to use another API key, use r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")
            # instead of r.recognize_google(audio)
            recog_results = r.recognize_google(audio)
            print("[speech recognition] Google Speech Recognition thinks you said \"" + recog_results + "\"")

            output_message("")
            if recog_results == "play" or recog_results == "start":
                client.send_message('/g', 1)
                stop_pitch = False 
                client.send_message('/setgame', 1)
                started = True 
                pitch_disabled = False
                ps("sounds/started.mp3")
            
            if recog_results == "score":
                subprocess.run("say test", shell=True)
         #       client.send_message('/scores')
            if recog_results == "stop": 
                stop_pitch = True
                pitch_disabled = True
                ps('sounds/paused.mp3')
               # output_message("Game paused.")
                client.send_message('/setgame', 0)
            if recog_results == "activate":
               # if (mode == 'p1' and cur_powerup != 1) or (mode == 'p2' and cur_powerup != 2): 
              #      ps("sounds/notavailable.mp3")
                client.send_message('/setbigpaddle', 0)  
            if recog_results == "level":
                ps("sounds/level.mp3")
            if recog_results == "hard":
                ps("sounds/hard.mp3")
                client.send_message('/setlevel', 2)
            if recog_results == "insane":
                ps("sounds/insane.mp3")
                client.send_message('/setlevel', 3)
            if recog_results == "easy":
                ps("sounds/easy.mp3")
                client.send_message('/setlevel', 1)
            if recog_results == "instruction" or recog_results == "instructions":
                ps("sounds/instructions.mp3")
                client.send_message('/setlevel', 1)
            if recog_results == "hi": 
                ps("sounds/hisent.mp3")
                client.send_message('/hi')
               
                
    
        except sr.UnknownValueError:
            print("[speech recognition] Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("[speech recognition] Could not request results from Google Speech Recognition service; {0}".format(e))
        
     

# -------------------------------------#

# example 2: pitch & volume detection
# -------------------------------------#
# PyAudio object.
p = pyaudio.PyAudio()
# Open stream.
stream = p.open(format=pyaudio.paFloat32,
    channels=1, rate=44100, input=True,
    frames_per_buffer=1024)
# Aubio's pitch detection.
pDetection = aubio.pitch("default", 2048,
    2048//2, 44100)
# Set unit.
pDetection.set_unit("Hz")
pDetection.set_silence(-40)

tts_lock = threading.Lock()

def output_message(message):
    # Run the TTS engine in a dedicated thread
    tts_thread = threading.Thread(target=_speak, args=(message,))
    tts_thread.daemon = True
    tts_thread.start()

def _speak(message):
    with tts_lock:
        engine.say(message)
        engine.runAndWait()

def y_to_audio(y_pos): 
    return int(num.interp(y_pos, [0, 450], [220, 440]))

def sense_microphone():
    global quit, debug, started, turn, stop_pitch

    if started or stop_pitch: 
        return
    
    while not quit:
        if not started:
            time.sleep(0.1)
            continue

        data = stream.read(1024, exception_on_overflow=False)
        samples = num.fromstring(data, dtype=aubio.float_type)
        pitch = pDetection(samples)[0]
        if pitch > 0:
            if turn == 1:
                move_on_pitch(pitch, 1)
            elif turn == 2:
                move_on_pitch(pitch, 2)

        if debug:
            print(f"[DEBUG] pitch: {pitch}, smoothed: {pitch}")


def move_on_pitch(pitch, player):
    global last_pitch_p1, last_pitch_p2
    pitch = max(260, min(pitch, 523))
    buffer = 20
    paddle_position = int((523 - pitch) / (523 - 260) * (450 - 2 * buffer)) + buffer
    client.send_message('/setpaddle', paddle_position)

# -------------------------------------#
# speech recognition thread
# -------------------------------------#
# start a thread to listen to speech
speech_thread = threading.Thread(target=listen_to_speech, args=())
speech_thread.daemon = True
speech_thread.start()

# pitch & volume detection
# -------------------------------------#
# start a thread to detect pitch and volume
microphone_thread = threading.Thread(target=sense_microphone, args=())
microphone_thread.daemon = True
microphone_thread.start()
# -------------------------------------#


# Play some fun sounds?
# -------------------------------------#


def ps(filepath):
    global voice_allowed 

    with audio_lock:  # Prevent overlapping audio
        playsound(filepath, False)

def hit(f):
    if f== 0: 
        print("hitsound")
        ps('sounds/click1.wav')
    
    elif f == 1:
        print("pingsound")
        ps('sounds/ping.wav')
    
    elif f == 2: 
        print("oobsound")
        ps('sounds/oob.wav')
    
    elif f == 3: 
        print("returnedsound")
        ps('sounds/return.wav')

hit(0) 
# -------------------------------------#

# OSC connection
# -------------------------------------#
# used to send messages to host
if mode == 'p1':
    host_port = host_port_1
    p1_in = True
   # output_message("Player 1 has connected")
if mode == 'p2':
    host_port = host_port_2
    p2_in = True
   # output_message("Player 2 has connected")

if (mode == 'p1') or (mode == 'p2'):
    client = udp_client.SimpleUDPClient(host_ip, host_port)
    print("> connected to server at "+host_ip+":"+str(host_port))
    
# -------------------------------------#
# Player OSC port
if mode == 'p1':
    player_port = player_1_port
if mode == 'p2':
    player_port = player_2_port

player_server = osc_server.ThreadingOSCUDPServer((player_ip, player_port), dispatcher_player)
player_server_thread = threading.Thread(target=player_server.serve_forever)
player_server_thread.daemon = True
player_server_thread.start()
# -------------------------------------#
client.send_message("/connect", player_ip)
client.send_message("/hi", player_ip)

# MAIN LOOP
# manual input for debugging
# -------------------------------------#
while True:
    m = input("> send: ")
    cmd = m.split(' ')
    if len(cmd) == 2:
        client.send_message("/"+cmd[0], int(cmd[1]))
    if len(cmd) == 1:
        client.send_message("/"+cmd[0], 0)
    

    # this is how client send messages to server
    # send paddle position 200 (it should be between 0 - 450):
#   client.send_message('/p', 200)
    # set level to 3:
  #  client.send_message('/l', 3)
    # start the game:
  #  client.send_message('/g', 1)
    # pause the game:
   # client.sen