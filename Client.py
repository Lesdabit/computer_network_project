import sys
from tkinter import *
from tkinter import ttk
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
    SPEED_0_5X = 4
    SPEED_1X = 5
    SPEED_2X = 6

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

        self.connectToServer()
        threading.Thread(target=self.recvRtspReply).start()

    def createWidgets(self):
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.speed = ttk.Combobox(self.master, values=['0.5x', '1x', '2x'], width=10)
        self.speed.current(1)
        self.speed.bind("<<ComboboxSelected>>", self.changeSpeed)
        self.speed.grid(row=1, column=2, padx=2, pady=2)

        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=3, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=4, padx=2, pady=2)

        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=5, sticky=W+E+N+S, padx=5, pady=5)

    def setupMovie(self):
        if self.state == self.INIT:
            print("Setting up movie...")
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        print("Exiting client...")
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

    def pauseMovie(self):
        if self.state == self.PLAYING:
            print("Pausing movie...")
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        if self.state == self.READY:
            print("Playing movie...")
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)

    def changeSpeed(self, event=None):
        print(f"Changing speed to {self.speed.get()}...")
        rtsp_speed = self.map_speed_to_rtsp(self.speed.get())
        print(rtsp_speed)
        self.sendRtspRequest(rtsp_speed)

    def map_speed_to_rtsp(self, speed):

        if speed == '0.5x':
            return self.SPEED_0_5X
        elif speed == '1x':
            return self.SPEED_1X
        elif speed == '2x':
            return self.SPEED_2X
        else:
            return self.SPEED_1X

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
                except Exception as e:
                    print(f"Error receiving RTP packet: {e}")
                    if self.playEvent.isSet():
                        return
                    if self.teardownAcked == 1:
                        self.rtpSocket.shutdown(socket.SHUT_RDWR)
                        self.rtpSocket.close()
                        return


    def writeFrame(self, data):
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        try:
            file = open(cachename, "wb")
            file.write(data)
            file.close()
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

        elif requestCode == self.SPEED_0_5X and (self.state == self.PLAYING or self.state == self.READY or self.state == self.INIT):
            request = f"SPEED_0_5X {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.SPEED_0_5X
        
        elif requestCode == self.SPEED_1X and (self.state == self.PLAYING or self.state == self.READY or self.state == self.INIT):
            request = f"SPEED_1X {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.SPEED_1X
        
        elif requestCode == self.SPEED_2X and (self.state == self.PLAYING or self.state == self.READY or self.state == self.INIT):
            request = f"SPEED_2X {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}"
            self.requestSent = self.SPEED_2X

        else:
            return

        self.rtspSocket.send(request.encode('utf-8'))
        print(f'Data sent:\n{request}')

    def recvRtspReply(self):
        while True:
            reply = self.rtspSocket.recv(1024)
            if reply:
                print(f"Received RTSP reply:\n{reply.decode('utf-8')}")
                self.parseRtspReply(reply.decode("utf-8"))

            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
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
