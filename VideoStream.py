import cv2
import os

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data: 
			framelength = int(data)
							
			# Read the current frame
			data = self.file.read(framelength)
			self.frameNum += 1
		return data
	def __init__(self, filename):
		self.filename = filename
		self.cap = cv2.VideoCapture(filename)
		self.frameNbr = 0

	# def nextFrame(self):
	# 	"""Get next frame."""
	# 	try:
	# 		ret, frame = self.cap.read()
	# 		if not ret:
	# 			print("Error: Unable to read frame from video")
	# 			return None

	# 		self.frameNbr += 1
	# 		frameFilename = f"cache-{self.frameNbr:06d}.jpg"
	# 		cv2.imwrite(frameFilename, frame)

	# 		# Debug information
	# 		print(f"Frame written to cache: {frameFilename}")

	# 		# Verify the written file
	# 		if not os.path.exists(frameFilename):
	# 			print(f"Error: Frame file {frameFilename} does not exist")
	# 			return None

	# 		if os.path.getsize(frameFilename) == 0:
	# 			print(f"Error: Frame file {frameFilename} is empty")
	# 			return None

	# 		return frameFilename
	# 	except Exception as e:
	# 		print(f"Error updating movie frame: {e}")
	# 		return None
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	