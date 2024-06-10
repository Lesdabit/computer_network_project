import sys
from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket
import threading
import os
from RtpPacket import RtpPacket
import time

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        print(f"Initializing client with serveraddr={serveraddr}, serverport={serverport}, rtpport={rtpport}, filename={filename}")
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.frameNbr = 0
        self.playback_speed = 1  # Default playback speed

        self.connectToServer()
        threading.Thread(target=self.recvRtspReply).start()

    def createWidgets(self):
        self.setup = Button(self.master, width=20, padx=3, pady=3, text="Setup", command=self.setupMovie)
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, padx=3, pady=3, text="Play", command=self.playMovie)
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.pause = Button(self.master, width=20, padx=3, pady=3, text="Pause", command=self.pauseMovie)
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, padx=3, pady=3, text="Teardown", command=self.exitClient)
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        self.playback_speed_label = Label(self.master, text="Playback Speed:")
        self.playback_speed_label.grid(row=2, column=0, padx=2, pady=2)

        self.playback_speed_selector = Spinbox(self.master, values=("0.5x", "1x", "2x"), width=5, command=self.changePlaybackSpeed)
        self.playback_speed_selector.grid(row=2, column=1, padx=2, pady=2)

        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

    def setupMovie(self):
        print("Setting up movie...")
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        print("Exiting client...")
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()
        cacheFileName = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        if os.path.exists(cacheFileName):
            os.remove(cacheFileName)

    def pauseMovie(self):
        print("Pausing movie...")
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        print("Playing movie...")
        if self.state == self.READY:
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)

    def listenRtp(self):
        print("Listening for RTP packets...")
        while True:
            if self.state == self.PLAYING:
                try:
                    data = self.rtpSocket.recv(20480)
                    if data:
                        print(f"RTP packet received, length: {len(data)}")
                        rtpPacket = RtpPacket()
                        rtpPacket.decode(data)
                        currFrameNbr = rtpPacket.seqNum()
                        print(f"Current Seq Num: {currFrameNbr}")
                        if currFrameNbr > self.frameNbr:
                            self.frameNbr = currFrameNbr
                            self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
                            time.sleep(0.5 / self.playback_speed)  # Adjust sleep time based on playback speed
                except Exception as e:
                    print(f"Error receiving RTP packet: {e}")
                    if self.playEvent.isSet():
                        return
                    if self.teardownAcked == 1:
                        self.rtpSocket.shutdown(socket.SHUT_RDWR)
                        self.rtpSocket.close()
                        return

    def changePlaybackSpeed(self):
        selected_speed = self.playback_speed_selector.get()
        if selected_speed == "0.5x":
            self.playback_speed = 0.5
        elif selected_speed == "1x":
            self.playback_speed = 1
        elif selected_speed == "2x":
            self.playback_speed = 2

    def writeFrame(self, data):
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        try:
            with open(cachename, "wb") as file:
                file.write(data)
            print(f"Frame written to cache: {cachename}")
            return cachename
        except Exception as e:
            print(f"Error writing frame to cache: {e}")
            return ""

    def updateMovie(self, imageFile):
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image=photo, height=288)
            self.label.image = photo
            print(f"Updated movie frame: {imageFile}")
        except Exception as e:
            print(f"Error updating movie frame: {e}")

    def connectToServer(self):
        print("Connecting to server...")
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
            print("Connected to server.")
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            tkinter.messagebox.showwarning('Connection Failed', f'Connection to {self.serverAddr} failed.')

    def sendRtspRequest(self, requestCode):
        self.rtspSeq += 1
        request = ""

        if requestCode == self.SETUP and self.state == self.INIT:
            request = f"SETUP {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nTransport: RTP/UDP; client_port= {self.rtpPort}"
            self.requestSent = self.SETUP

        elif requestCode == self.PLAY and self.state == self.READY:
            request = f"PLAY {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.PLAY

        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            request = f"PAUSE {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.PAUSE

        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            request = f"TEARDOWN {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.TEARDOWN

        else:
            return

        self.rtspSocket.send(request.encode('utf-8'))
        print(f'Data sent:\n{request}')

    def recvRtspReply(self):
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
                if reply:
                    print(f"Received RTSP reply:\n{reply.decode('utf-8')}")
                    self.parseRtspReply(reply.decode("utf-8"))

                if self.requestSent == self.TEARDOWN:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
                    break
            except Exception as e:
                print(f"Error receiving RTSP reply: {e}")
                break
    
    def parseRtspReply(self, data):
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])
        
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            if self.sessionId == 0:
                self.sessionId = session
            
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        self.state = self.READY
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        self.teardownAcked = 1 

    def openRtpPort(self):
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.settimeout(0.5)
        
        try:
            self.rtpSocket.bind(("", self.rtpPort))
        except:
            tkinter.messagebox.showwarning('Unable to Bind', f'Unable to bind PORT={self.rtpPort}')

    def handler(self):
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Usage: python Client.py <ServerIP> <ServerPort> <RTPPort> <VideoFile>")
        exit(1)

    root = Tk()
    client = Client(root, sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    root.mainloop()
