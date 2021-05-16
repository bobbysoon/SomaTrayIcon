#!/usr/bin/env python3

import os,sys,math,urllib.request,pickle,locale,mpv

def sgn(n): return -1 if n<0 else 1 if n>0 else 0

def Cache(url):
	n = url[url.rfind('/')+1:]
	fpCfg = os.path.expanduser('~/.config/somaTray/')
	fp = fpCfg + n
	if not os.path.isfile(fp):
		print('requesting "%s"...'%url,end='',flush=True)
		url = 'https://somafm.com' + url
		urllib.request.urlretrieve(url, fp)
		print()
	return fp

class Channel:
	def __init__(self, name, genres, href, imgsrc):
		self.name = name
		self.href = href
		self.genres = genres
		self.imgFp = Cache(imgsrc) # downloads image

class Soma(object):
	@staticmethod
	def Scrape():
		fpListen = Cache('/listen') # the webpage with the channels
		if os.path.isfile(fpListen):
			with open(fpListen,'rt') as h: t=h.read()
			
			# scrape channels
			channels = []
			i = t.find('Start of Stations')
			while i>-1:
				i = t.find('Channel:', i)
				if i>-1:
					i+= 9
					j = t.find('Listeners:', i)-1
					channel = t[i:j]
					
					i = t.find('<!--', j)+5
					j = t.find('-->', i)-1
					label = t[i:j]
					
					i = t.find('<img src="', j)+10
					j = t.find('"', i)
					imgsrc = t[i:j]
					
					i = t.find('<a href="', j)+9
					j = t.find('"', i)
					href = t[i:j]
					
					a=label.split(' ')
					genres = a.pop().strip('()').split('/')
					name = ' '.join(a)
					
					channels.append( Channel(name, genres, href, imgsrc) )
			
			return channels
	
	def __new__(cls):
		self = object.__new__(cls)
		self.channels = Soma.Scrape()
		if self.channels: return self
	def __init__(self):
		object.__init__(self)
		
		self.genres,self.channelNames = dict(),dict()
		for channel in self.channels:
			self.channelNames[channel.name] = channel
			
			for genre in channel.genres:
				if not genre in self.genres:
					self.genres[genre] = {}
				self.genres[genre][channel.name] = channel

soma = Soma()

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class Config(QObject):
	# config defaults
	genre = 'electronic'
	channel = 'Groove Salad'
	volume = 50.0
	
	saveDelay = 3000
	fpCfg = '~/.config/somaTray/'
	
	saveKeys = 'genre,channel,volume'.split(',')
	
	def __init__(self):
		QObject.__init__(self)
		self.load()
		self.saveDelayTimer = QTimer()
		self.saveDelayTimer.setSingleShot(True)
		self.saveDelayTimer.timeout.connect(self.save)
	
	def load(self):
		fpCfg = os.path.expanduser(self.fpCfg)
		fp = fpCfg+'soma.pickle'
		if os.path.isfile(fp):
			with open( fp, "rb" ) as h:
				d = pickle.load( h )
			d = {k:d[k] for k in d if k in self.saveKeys}
			self.__dict__.update(d)
			print('config loaded:',d)
	
	def save(self):
		fpCfg = os.path.expanduser(self.fpCfg)
		if not os.path.isdir(fpCfg):
			os.makedirs(fpCfg)
		
		fp = fpCfg+'soma.pickle'
		d = {k:self.__dict__[k] for k in self.__dict__ if k in self.saveKeys}
		with open(fp,"wb") as h:
			pickle.dump(d,h)
		
		print('config saved:',d)
	
	def delayedSave(self):
		self.saveDelayTimer.start(self.saveDelay)

config = Config()

class Player(mpv.MPV,QObject): # <- here, the order matters
	#started = pyqtSignal(object) # player volumes, this up, others down
	titleChanged = pyqtSignal(str)
	def __init__(self):
		QObject.__init__(self)
		mpv.MPV.__init__(self) # <- maybe here too
		self.observe_property('media-title', self.media_title)
		self.volume = 0.0
	def media_title(self, n,v):
		if type(v) is bytes: c = v.decode('UTF-8')
		if v: self.titleChanged.emit(v)

class ToolTip(QWidget):
	fadeDelay = 1000
	fadeInterval = 50
	fadeStep = .1
	def __init__(self):
		QWidget.__init__(self)
		self.setWindowFlags(Qt.ToolTip | Qt.Dialog)
		self.fadeTimer = QTimer();self.fadeTimer.setSingleShot(True)
		self.fadeTimer.timeout.connect(self.fadeOut)
	def fadeOut(self):
		v = self.windowOpacity()-self.fadeStep
		if v>0:
			self.setWindowOpacity(v);self.update()
			self.fadeTimer.start(ToolTip.fadeInterval)
		else:
			self.hide()
	def enterEvent(self, e):
		self.fadeTimer.stop()
		self.setWindowOpacity(1.0)
	def leaveEvent(self, e):
		self.fadeTimer.start(self.fadeDelay)
	def showOverTrayIcon(self, trayIconGeometry):
		if not self.isVisible():
			QWidget.show(self) ; g=self.geometry() # place over tray icon
			#g.setSize(QSize(320,320))
			g.moveCenter(trayIconGeometry.center())
			g.moveBottom(trayIconGeometry.top())
			self.setGeometry(g)
		self.setWindowOpacity(1.0)
		self.fadeTimer.start(self.fadeDelay)

class Tuner(ToolTip):
	channelSelected = pyqtSignal(object)
	
	def __init__(self, genres):
		ToolTip.__init__(self)
		self.genres = genres
		
		self.image = QLabel()
		self.genresList = QListWidget()
		self.channelsList = QListWidget() 
		self.btArtistSong = QPushButton()
		
		lVLayout = QVBoxLayout();lVLayout.setContentsMargins(0,0,0,0);lVLayout.setSpacing(0)
		lVLayout.addWidget(self.genresList)
		lVLayout.addWidget(self.image)
		
		rVLayout = QVBoxLayout();rVLayout.setContentsMargins(0,0,0,0);rVLayout.setSpacing(0)
		rVLayout.addWidget(self.channelsList)
		rVLayout.addWidget(self.btArtistSong)
		
		hLayout = QHBoxLayout();hLayout.setContentsMargins(0,0,0,0);hLayout.setSpacing(0)
		hLayout.addLayout(lVLayout)
		hLayout.addLayout(rVLayout)
		self.setLayout(hLayout)
		
		self.image.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
		self.genresList.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored)
		self.channelsList.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Preferred)
		self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
		
		self.populateGenresList()
		
		self.genresList.currentRowChanged.connect(self.genresListRowChanged)
		self.channelsList.currentRowChanged.connect(self.channelsListRowChanged)
		self.channelsList.itemDoubleClicked.connect(self.channelsListItemDoubleClicked)
		self.btArtistSong.clicked.connect(self.copyArtistSongToClipboard)
	
	def setArtistSong(self, title):
		self.btArtistSong.setText(title)
		self.btArtistSong.setToolTip(title)
	def copyArtistSongToClipboard(self):
		QApplication.clipboard().setText(self.btArtistSong.text())
	
	def populateGenresList(self):
		self.genreNames = sorted(self.genres.keys())
		self.genresList.addItems(self.genreNames)
	
	def populateChannelsList(self):
		self.channelsList.currentRowChanged.disconnect(self.channelsListRowChanged)
		
		self.channelsList.clear()
		gRow = self.genresList.currentRow()
		if gRow>-1:
			gName = self.genreNames[gRow]
			gChannels = self.genres[gName]
			self.channelNames = sorted(gChannels.keys())
			self.genreChannels = [gChannels[cName] for cName in self.channelNames]
			self.channelsList.addItems(self.channelNames)
			
			for i in range(len(self.channelNames)):
				item = self.channelsList.item(i)
				cName = self.channelNames[i]
				channel = self.genres[gName][cName]
				item.setIcon(QIcon(channel.pixmap))
			
		self.channelsList.currentRowChanged.connect(self.channelsListRowChanged)
	
	def genresListRowChanged(self, row):
		self.populateChannelsList()
		config.genre = self.genreNames[row]
	
	def channelsListRowChanged(self, row):
		self.channelSelected.emit( self.genreChannels[row] )
	
	def channelsListItemDoubleClicked(self, item):
		self.channelsListRowChanged(self.row(item))
	
	def selectGenre(self, genreName):
		r= self.genreNames.index(genreName)
		self.genresList.setCurrentRow(r)
	
	def selectChannel(self, channel):
		self.selectGenre(channel.genres[0])
		
		r= self.channelNames.index(channel.name)
		self.channelsList.setCurrentRow(r)

class VolControl(QTimer):
	volume = config.volume
	players = set()
	playing = None
	fadeStep = 1
	fadeInterval = 25
	stepped = pyqtSignal()
	def __init__(self):
		QTimer.__init__(self)
		self.setInterval(self.fadeInterval)
		self.setSingleShot(False)
		self.timeout.connect(self.step)
	def start(self):
		if not self.isActive():
			QTimer.start(self)
	def step(self):
		stopFader = True
		for player in list(self.players):
			volGoal = self.volume if player == self.playing else 0.0
			volDiff = volGoal - player.volume
			if abs(volDiff) > self.fadeStep:
				player.volume+= self.fadeStep * sgn(volDiff)
				stopFader = False
			else:
				player.volume = volGoal
				if not volGoal:
					player.quit()
					self.players.remove(player)
					if player == self.playing:
						self.playing = None
		if stopFader:
			self.stop()
		
		self.stepped.emit()

class ContextMenu(QMenu):
	def __init__(self, quit):
		QMenu.__init__(self)
		
		quit_action = QAction(QIcon.fromTheme('application-exit'),'Exit',self)
		quit_action.triggered.connect(quit)
		self.addAction(quit_action)

class TrayIcon(QSystemTrayIcon):
	scrolled = pyqtSignal(int)
	clicked = pyqtSignal(object)
	def __init__(self):
		QSystemTrayIcon.__init__(self)
		self.setContextMenu(ContextMenu(self.onQuit))
		self.activated.connect(self.onActivated)
		
		self.setIcon(QIcon.fromTheme('network-error'))
		self.show()
		self.iconSize = self.geometry().size()
	
	def onActivated(self, reason):
		global window
		if reason == QSystemTrayIcon.Trigger:
			self.clicked.emit(self.geometry())
		elif reason == QSystemTrayIcon.Context:
			if hasattr(self,'tuner') and self.tuner.isVisible():
				self.tuner.hide()
			self.contextMenu().popup(self.geometry().topLeft())
		else:
			print('TrayIcon.onActivated(reason:{})'.format(type(reason)))
	
	def event(self, e):
		def sgn(n): return -1 if n<0 else 1 if n>0 else 0
		if type(e) == QWheelEvent:
			self.scrolled.emit(sgn(e.angleDelta().y()))
		#else:
		#	print(type(e),e)
		return QSystemTrayIcon.event(self,e)

class SomaTrayIcon(TrayIcon):
	def __init__(self, soma):
		TrayIcon.__init__(self)
		
		if soma:
			self.lSomaPixmap = QPixmap(Cache('/img3/LoneDJsquare400.jpg'))
			self.somaPixmap = self.lSomaPixmap.scaled(self.iconSize)
			for channel in soma.channels:
				channel.lPixmap = QPixmap(channel.imgFp)
				channel.pixmap = channel.lPixmap.scaled(self.iconSize)
			
			self.tuner = Tuner(soma.genres)
			self.tuner.channelSelected.connect(self.playChannel)
			self.clicked.connect(self.tuner.showOverTrayIcon)
			
			self.scrolled.connect(self.adjustVolume)
			
			self.volControl = VolControl()
			self.volControl.stepped.connect(self.onVolControlStepped)
			
			self.tuner.image.setPixmap(self.lSomaPixmap)
			self.tuner.selectChannel(soma.channelNames[config.channel])
		else:
			print('network error')
			self.setToolTip('SomaTrayIcon:\ntrouble connecting\nwith somafm.com')
	
	def modHeld(self):
		anyMod = Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier
		return anyMod & int(QApplication.keyboardModifiers())
	
	def adjustVolume(self, d):
		global config
		
		vol = self.volControl.volume ; fadeStep = self.volControl.fadeStep
		if self.modHeld(): fadeStep*= 3
		vol = min(100.0,max(0.0,vol + fadeStep * d))
		
		self.volControl.volume = vol
		self.volControl.start()
		
		if config.volume != vol:
			config.volume = vol
			config.delayedSave()
	
	def playChannel(self, channel):
		global config
		
		self.tuner.image.setPixmap(channel.lPixmap)
		
		player = Player() ; self.volControl.playing = player ; self.volControl.players.add(player)
		player.titleChanged.connect(self.onTitleChanged)
		player.play('http://somafm.com'+channel.href) ; player.channel = channel
		self.volControl.start()
		
		if config.channel != channel.name:
			config.channel = channel.name
			config.delayedSave()
	
	def onTitleChanged(self, title):
		self.tuner.setArtistSong(title)
	
	def onVolControlStepped(self):
		va = [(player.volume,player.channel.pixmap) for player in self.volControl.players]
		f = sum([a for a,b in va])
		
		pixmap = QPixmap(self.somaPixmap)
		painter = QPainter(pixmap)
		
		for v,pm in va:
			if self.volControl.volume:
				painter.setOpacity(v/self.volControl.volume)
				painter.drawPixmap(0,0,pm)
		
		painter.setOpacity(1.0)
		
		cx,cy = self.iconSize.width()/2,self.iconSize.height()/2
		a = 0.78535 + 4.7123895*self.volControl.volume/100.0
		xx,yy = -math.sin(a)*cx,math.cos(a)*cy
		x1,y1 = cx+xx*.5 , cy+yy*.5
		x2,y2 = cx+xx*.8 , cy+yy*.8
		pen = QPen(Qt.black) ; pen.setCapStyle(Qt.RoundCap) ; pen.setWidth(4)
		painter.setRenderHint(QPainter.Antialiasing)
		painter.setPen(pen)
		painter.drawLine(int(x1),int(y1),int(x2),int(y2))
		pen.setColor(Qt.cyan);pen.setWidth(3);painter.setPen(pen)
		painter.drawLine(int(x1),int(y1),int(x2),int(y2))
		
		painter.end() ; del painter
		
		self.setIcon(QIcon(pixmap))
		
		if self.quitting and not self.volControl.players:
			qApp.quit()
		elif not (self.quitting or self.volControl.players):
			self.playChannel(soma.channelNames[config.channel])
	
	quitting = False
	def onQuit(self):
		if hasattr(self,'volControl'):
			self.quitting = True
			self.volControl.playing = None
			self.volControl.start()
		else:
			qApp.quit()

app = QApplication(sys.argv)
locale.setlocale(locale.LC_NUMERIC, 'C') # mpv needs this
somaTrayIcon = SomaTrayIcon(soma)
sys.exit(app.exec())
