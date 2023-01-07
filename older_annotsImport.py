from PySide2 import QtWidgets, QtCore, QtGui
from maya import OpenMayaUI as omui
from shiboken2 import wrapInstance
from shotgun import shotgun as sg
from bd_scene_info import SceneInfo

import maya.cmds as cmds
import os
import sys
import platform
import json

#Use NSURL as a workaround to pyside/Qt4 behaviour for dragging and dropping on OSx
if platform.system() == 'Darwin':
	from Foundation import NSURL

def _maya_main_window():
	for obj in QtWidgets.qApp.topLevelWidgets():
		if obj.objectName() == 'MayaWindow':
			return obj
	raise RuntimeError('Could not find MayaWindow instance')

def hex2QColor(c):
	#Convert Hex color to QColor
	r = int(c[0:2], 16)
	g = int(c[2:4], 16)
	b = int(c[4:6], 16)
	
	return QtGui.QColor(r, g, b)

class annImport(QtWidgets.QMainWindow):
	def __init__(self, parent):
		super(annImport, self).__init__(parent)
		
		self.iconsPath = "<HERE>"
		
		self.borderRadius = 5
		self.backgroundColor = hex2QColor("44444c")
		self.foregroundColor = hex2QColor("44444c")
		self.draggable = True
		self.dragging_threshould = 5
		
		self.loaded = True
		self.nodeStarted = False
		self.strokeStarted = False
		self.nodeStruct = []
		self.strokeStruct = {}
		
		self.createGUI()
	
	def msg(self, text="", type=0):
		types = [0x366032, 0x605e32, 0x603232]
		cmds.inViewMessage(smg=text, pos='botRight', fade=True, bkc=types[type], fst=3500)
		print(text)
	
	def createGUI(self):		
		self.setWindowTitle('Drop Annotations Here!')
		self.setObjectName('annImportObj')
		self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
		self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
		self.setGeometry(1200, 400, 260, 200)
		self.setMaximumSize(260,200)
		self.setMinimumSize(260,200)
		self.setProperty("saveWindowPref", True)

		#Widget setup
		self.widget = QtWidgets.QWidget()
		
		self.boxLay = QtWidgets.QHBoxLayout()
		self.dropFrame = QtWidgets.QFrame()
		self.dropFrame.setFrameShadow(QtWidgets.QFrame.Sunken)
		self.dropFrame.setLineWidth(3)
		
		self.dropFrame.setStyleSheet('background:#333333 url('+self.iconsPath+'annImport_dropIcon.png) no-repeat center middle; border-radius: 6px;')
		self.boxLay.addWidget(self.dropFrame)
		self.widget.setLayout(self.boxLay)
		
		self.setCentralWidget(self.widget)
		
		self.sgGrabBtn = QtWidgets.QPushButton(self)
		self.sgGrabBtn.setText("Grab Latest")
		self.sgGrabBtn.setToolTip("Grab latest from Shotgun")
		self.sgGrabBtn.setIcon(QtGui.QIcon(self.iconsPath+'sg.png'))
		self.sgGrabBtn.setStyleSheet('QPushButton {background:#55665d; color:#cccccc; border-radius:6px; font:12px Segoe UI; font-weight:bold;} QPushButton:hover {background-color:#44664c;} QPushButton:pressed {background-color:#33443b;}')
		self.sgGrabBtn.setGeometry(16, 16, 100, 24)
		self.sgGrabBtn.clicked.connect(self.getAnnFromSG)
		
		self.brsFileBtn = QtWidgets.QPushButton(self)
		self.brsFileBtn.setText("Browse")
		self.brsFileBtn.setToolTip("Browse for file to import")
		self.brsFileBtn.setIcon(QtGui.QIcon(':/fileOpen.png'))
		self.brsFileBtn.setStyleSheet('QPushButton {background:#99885d; color:#cccccc; border-radius:6px; font:12px Segoe UI; font-weight:bold;} QPushButton:hover {background-color:#88774c;} QPushButton:pressed {background-color:#77663b;}')
		self.brsFileBtn.setGeometry(125, 16, 100, 24)
		self.brsFileBtn.clicked.connect(self.browseForAnn)
		
		self.closeBtn = QtWidgets.QPushButton(self)
		self.closeBtn.setText("X")
		self.closeBtn.setToolTip("Close")
		self.closeBtn.setStyleSheet('QPushButton {background:#44444c; color:#cccccc; border-radius:4px; font:12px MS Shell Dlg 2; font-weight:bold;} QPushButton:hover {background-color:#55555d;} QPushButton:pressed {background-color:#33333d;}')
		self.closeBtn.setGeometry(232, 4, 24, 24)
		self.closeBtn.clicked.connect(self.closeIt)
		
		# Enable dragging and dropping onto the GUI
		self.setAcceptDrops(True)
		
		self.show()
	
	def mousePressEvent(self, event):
		if self.draggable and event.button() == QtCore.Qt.LeftButton:
			self.__mousePressPos = event.globalPos()                # global
			self.__mouseMovePos = event.globalPos() - self.pos()    # local
		super(annImport, self).mousePressEvent(event)

	def mouseMoveEvent(self, event):
		if self.draggable and event.buttons() & QtCore.Qt.LeftButton:
			globalPos = event.globalPos()
			moved = globalPos - self.__mousePressPos
			if moved.manhattanLength() > self.dragging_threshould:
				# move when user drag window more than dragging_threshould
				diff = globalPos - self.__mouseMovePos
				self.move(diff)
				self.__mouseMovePos = globalPos - self.pos()
		super(annImport, self).mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		if self.__mousePressPos is not None:
			if event.button() == QtCore.Qt.LeftButton:
				moved = event.globalPos() - self.__mousePressPos
				if moved.manhattanLength() > self.dragging_threshould:
					# do not call click event or so on
					event.ignore()
				self.__mousePressPos = None
		super(annImport, self).mouseReleaseEvent(event)

		# close event
		if event.button() == QtCore.Qt.RightButton:
			self.close()
	
	def paintEvent(self, event):
		# get current window size
		s = self.size()
		qp = QtGui.QPainter()
		qp.begin(self)
		qp.setRenderHint(QtGui.QPainter.Antialiasing, True)
		qp.setPen(self.foregroundColor)
		qp.setBrush(self.backgroundColor)
		qp.drawRoundedRect(0, 0, s.width(), s.height(), self.borderRadius, self.borderRadius)
		qp.end()
	
	def dragEnterEvent(self, event):
		if event.mimeData().hasUrls:
			event.accept()
		else:
			event.ignore()

	def dragMoveEvent(self, event):
		if event.mimeData().hasUrls:
			event.accept()
		else:
			event.ignore()

	def dropEvent(self, event):
		if event.mimeData().hasUrls:
			event.setDropAction(QtCore.Qt.CopyAction)
			event.accept()
			# Workaround for OSx dragging and dropping
			for url in event.mimeData().urls():
				if platform.system() == 'Darwin':
					filename = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path())
				else:
					filename = str(url.toLocalFile())

			if filename.endswith(".rv"): #RV file
				self.annFile = filename
				self.doImport(annFile=self.annFile, annType="rv")
			elif filename.endswith(".kpro"): #Keyframe Pro file
				self.annFile = filename
				self.doImport(annFile=self.annFile, annType="kpro")
			else:
				self.msg(text="Drag either <hl>RV</hl> or <hl>KeyframePro</hl> format", type=1)
		else:
			event.ignore()
	
	def resetData(self):
		self.loaded = True
		self.nodeStarted = False
		self.strokeStarted = False
		self.nodeStruct = []
		self.strokeStruct = {}
	
	def doImport(self, annFile="", annType=""):
		self.resetData()
		cmds.undoInfo(openChunk=True)
		try:
			if not self.fileInterprete(filename=annFile, fType=annType):
				self.msg(text="Failed to <hl>interpret</hl> annoations file.", type=2)
				cmds.undoInfo(closeChunk=True)
				return
			
			if not self.getStrokesData():
				self.msg(text="Failed to get <hl>stroke data</hl>.", type=2)
				cmds.undoInfo(closeChunk=True)
				return
			
			thisCam = self.getCamera()
			if not thisCam:
				self.msg(text="Failed to get <hl>Camera</hl>.", type=2)
				cmds.undoInfo(closeChunk=True)
				return
			
			#Get camera's near clipping plane
			ncp = cmds.getAttr(thisCam+".nearClipPlane")
			fl = cmds.getAttr(thisCam+".focalLength")
			cData = self.createController(0.5 * ncp / fl)
			
			strokesData = self.createStrokes(fType=annType, ctrlData=cData)
			if not strokesData:
				self.msg(text="Failed to get <hl>stroke data</hl>.", type=2)
				cmds.undoInfo(closeChunk=True)
				return
			
			#parent controller to the group
			cmds.parent(cData[0], strokesData['crvGRP'])
			
			#Constraint curves group to camera and set clipping plane
			cmds.parentConstraint(thisCam, strokesData['crvGRP'], weight=1)
			
			#Attach scale to Focal Length multiplied by Horizontal Aperture
			scaleVals_pub = {"rv": [15.789*ncp, 15.789*ncp, 15.789*ncp], "kpro": [14.411*ncp, 13.697*ncp, 45.697*ncp]}
			scaleVals_loc = {"rv": [15.789*ncp, 15.789*ncp, 15.789*ncp], "kpro": [13.400*ncp, 13.697*ncp, 42.530*ncp]}
			
			bcNode = cmds.createNode("blendColors", name="bc_camAnn_matching01")
			cmds.setAttr(bcNode+".color2R", scaleVals_pub[annType][0])
			cmds.setAttr(bcNode+".color2G", scaleVals_pub[annType][1])
			cmds.setAttr(bcNode+".color2B", scaleVals_pub[annType][2])
			cmds.setAttr(bcNode+".color1R", scaleVals_loc[annType][0])
			cmds.setAttr(bcNode+".color1G", scaleVals_loc[annType][1])
			cmds.setAttr(bcNode+".color1B", scaleVals_loc[annType][2])
			cmds.connectAttr(cData[1]+".Match", bcNode+".blender", f=True)
			
			mdNode1 = cmds.createNode("multiplyDivide", name="camAnnFL_mult01")
			cmds.connectAttr(bcNode+".outputR", mdNode1+".input1X", f=True)
			cmds.connectAttr(bcNode+".outputG", mdNode1+".input1Y", f=True)
			cmds.connectAttr(bcNode+".outputB", mdNode1+".input1Z", f=True)
			cmds.connectAttr(thisCam+".horizontalFilmAperture", mdNode1+".input2X", f=True)
			cmds.connectAttr(thisCam+".horizontalFilmAperture", mdNode1+".input2Y", f=True)
			cmds.connectAttr(thisCam+".horizontalFilmAperture", mdNode1+".input2Z", f=True)
			
			mdNode2 = cmds.createNode("multiplyDivide", name="camAnnFL_mult02")
			
			cmds.connectAttr(mdNode1+".outputX", mdNode2+".input1X", f=True)
			cmds.connectAttr(mdNode1+".outputY", mdNode2+".input1Y", f=True)
			cmds.connectAttr(mdNode1+".outputZ", mdNode2+".input1Z", f=True)
			cmds.connectAttr(thisCam+".focalLength", mdNode2+".input2X", f=True)
			cmds.connectAttr(thisCam+".focalLength", mdNode2+".input2Y", f=True)
			cmds.connectAttr(thisCam+".focalLength", mdNode2+".input2Z", f=True)
			cmds.setAttr(mdNode2+".operation", 2)
			
			cmds.connectAttr(mdNode2+".outputX", strokesData['offsetGRP']+".scaleX", f=True)
			cmds.connectAttr(mdNode2+".outputY", strokesData['offsetGRP']+".scaleY", f=True)
			cmds.connectAttr(mdNode2+".outputZ", strokesData['offsetGRP']+".scaleZ", f=True)
			
			cmds.select(cl=True)
			
			self.msg(text="Annotations Loaded!", type=0)

			cmds.undoInfo(closeChunk=True)
		except:
			cmds.undoInfo(closeChunk=True)
			raise
	
	def getAnnFromSG(self):
		formats = ['rv', 'kpro']
		thisSG = sg.Shotgun()
		
		#Get scene data
		this_scene = cmds.file(query=True, sceneName=True)
		if not SceneInfo().is_valid_file_path(this_scene):
			self.msg(text="Tool only works inside a <hl>pipeline scene</hl>.", type=2)
			return False
		
		self.scene_info = SceneInfo(this_scene)
		
		#Find current shot
		shotCode = "_".join([self.scene_info.name_show,
					   self.scene_info.season+self.scene_info.episode,
					   self.scene_info.seq,
					   self.scene_info.shot]
		)
		shot = thisSG.find('Shot', [['code', 'is', shotCode]])
		
		if not shot:
			self.msg(text="Current shot was <hl>not found</hl> on Shotgun.", type=1)
			return False
		
		#Get attachments for all notes on current shot, newest first
		notes = thisSG.find('Note',
						[["note_links", "is", shot]],
						["attachments"],
						[{'field_name':'created_at', 'direction':'desc'}]
		)
		
		for note in notes:
			if len(note['attachments']) <= 0:
				continue
			
			for attachment in note['attachments']:
				ext = attachment['name'][attachment['name'].rfind('.')+1:]
				if ext not in formats:
					continue
				
				#Get file
				tempFile = thisSG.download_attachment(attachment['id'], file_path="C:/temp/tmpAnnotations."+ext)
				
				#Import
				if tempFile:
					self.doImport(annFile=tempFile, annType=ext)
					return True
		
		self.msg(text="<hl>No annotations found</hl> for current shot.", type=1)
		return False
	
	def browseForAnn(self):
		fname = QtWidgets.QFileDialog.getOpenFileName(self, 'Pick RV or Keyframe Pro', ':/', "Annotation files (*.rv *.kpro)")
		if fname[0] != '' and (fname[0].endswith('.rv') or fname[0].endswith('.kpro')):
			if fname[0].endswith('.rv'):
				self.doImport(annFile=fname[0], annType="rv")
			else:
				self.doImport(annFile=fname[0], annType="kpro")
	
	def closeIt(self):
		self.close()
		return
	
	def getCamera(self):
		cams = cmds.ls(type="camera")
		for cam in cams:
			if cam.endswith("Render_CamShape"):
				camTrans = cmds.listRelatives(cam, parent=True)
				if camTrans is not None:
					return camTrans[0]
		return "persp"
	
	def createController(self, scale=1.0):
		#Create controller shape
		iconFaces = [0,1,2]
		iconFaces[0] = cmds.polyCreateFacet(ch=True, tx=1, s=1, p=([-0.133918, 0, 0.0959791], [0.153527, 0, 0.379376], [0.465263, 0, 0.660748], [0.772951, 0, 0.91378], [0.862019, 0, 0.976533], [0.934892, 0, 1.004872], [0.975377, 0, 0.996775], [0.99562, 0, 0.97046], [0.99562, 0, 0.915805], [0.963232, 0, 0.828762], [0.878213, 0, 0.697185], [0.712223, 0, 0.460346], [0.438948, 0, 0.110149], [0.252716, 0, -0.108471], [0.157576, 0, -0.219806], [-0.133628, 0, 0.0960829]))[0]
		iconFaces[0] = cmds.rename(iconFaces[0], "annotations_CTRL")
		
		iconFaces[1] = cmds.polyCreateFacet(ch=True, tx=1, s=1, p=([-0.0560332, 0, -0.464492], [0.0914648, 0, -0.298221], [-0.203531, 0, 0.0235924], [-0.359074, 0, -0.137314], [-0.056005, 0, -0.464414]))[0]
		iconFaces[1] = cmds.rename(iconFaces[1], "annotations_ctrl02")

		iconFaces[2] = cmds.polyCreateFacet(ch=True, tx=1, s=1, p=([-0.120965, 0, -0.533467], [-0.424428, 0, -0.212383], [-0.532109, 0, -0.228045], [-0.635874, 0, -0.278949], [-0.723976, 0, -0.378798], [-0.780754, 0, -0.519762], [-0.810121, 0, -0.662684], [-0.831657, 0, -0.750786], [-0.872772, 0, -0.811479], [-0.943253, 0, -0.842804], [-0.978494, 0, -0.854551], [-0.988284, 0, -0.878045], [-0.98241, 0, -0.913286], [-0.955, 0, -0.930906], [-0.872772, 0, -0.956358], [-0.759217, 0, -0.983768], [-0.628043, 0, -0.995515], [-0.490995, 0, -0.975936], [-0.361778, 0, -0.921117], [-0.252139, 0, -0.831057], [-0.193404, 0, -0.737081], [-0.150332, 0, -0.6294], [-0.120943, 0, -0.533324]))[0]
		iconFaces[2] = cmds.rename(iconFaces[2], "annotations_ctrl03")

		thisShapes = cmds.listRelatives(iconFaces[1], shapes=True) + cmds.listRelatives(iconFaces[2], shapes=True)
		cmds.parent(thisShapes, iconFaces[0], r=True, s=True)
		cmds.delete([iconFaces[1], iconFaces[2]])
		
		thisCtrl = iconFaces[0]
		
		#Set shapes' attributes
		for shape in cmds.listRelatives(thisCtrl, shapes=True):
			cmds.setAttr(shape+".primaryVisibility", 0)
			cmds.setAttr(shape+".hideOnPlayback", 1)
		
		#Create Temp shader, if doesn't exist, and assign to new mesh
		if not cmds.objExists("annTempMtl"):
			tmpShdr = cmds.shadingNode("surfaceShader", asShader=True, name="annTempMtl")
			tmpSG = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="annTempMtlSG")
			cmds.connectAttr(tmpShdr+".outColor", tmpSG+".surfaceShader", f=True)
			cmds.setAttr(tmpShdr+".outColor", 0.175, 0.0, 0.0, type="double3")
		
		cmds.sets(thisCtrl, e=True, forceElement="annTempMtlSG")
		
		cmds.select(thisCtrl, r=True)
		cmds.DeleteHistory()
		
		#Create posGRP for controller
		pGrp = cmds.group(thisCtrl, name=thisCtrl+"_posGRP")
		
		#Create Attributes
		cmds.addAttr(thisCtrl, ln="Visible", at="long", min=0, max=1, dv=1)
		cmds.setAttr(thisCtrl+".Visible", e=True, keyable=True)
		
		cmds.addAttr(thisCtrl, ln="Opacity", at="float", min=0, max=10, dv=10)
		cmds.setAttr(thisCtrl+".Opacity", e=True, keyable=True)
		
		cmds.addAttr(thisCtrl, ln="Match", at="enum", en="Published:Local:")
		cmds.setAttr(thisCtrl+".Match", e=True, cb=True)
		
		mdNode = cmds.createNode('multiplyDivide', name="md_annBrushOpacity_mult01")
		cmds.connectAttr(thisCtrl+".Opacity", mdNode+".input1X", f=True)
		cmds.setAttr(mdNode+".input2X", 0.1)
		
		#Lock and hide attributes
		cmds.setAttr(thisCtrl+".translateX", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".translateY", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".translateZ", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".rotateX", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".rotateY", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".rotateZ", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".scaleX", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".scaleY", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".scaleZ", lock=True, cb=False, k=False)
		cmds.setAttr(thisCtrl+".visibility", lock=True, cb=False, k=False)
		
		#Scale posGRP
		cmds.scale(scale, scale, scale, pGrp, a=True)
		
		return [pGrp, thisCtrl, mdNode]
	
	def createStrokes(self, fType="", ctrlData=[]):
		if not self.strokeStruct:
			return False
		
		strkWidths = {'rv':0.5, 'kpro':1.0}
		
		#Delete previous annotations (There can be only ONE!)
		annotGroups = cmds.ls("rvDrawing*", type="transform")
		for grp in annotGroups:
			if cmds.attributeQuery("rvAnnotations", node=grp, exists=True):
				cmds.delete(grp)
		
		strokes = []
		curves = []
		brushes = []
		for strk in self.strokeStruct:
			strkParts = strk.replace('"', '').split(":")
			tool = strkParts[0]
			index = int(strkParts[1])
			frame = float(strkParts[2])
			author = strkParts[3]
			
			points = []
			knots = []
			k = 0
			for point in self.strokeStruct[strk]['points']:
				points.append([point[0], 0, point[1]])
				knots.append(k)
				k += 1
			
			#Create stroke curve
			thisCurve = cmds.curve(d=1, p=points, k=knots, name="crv_rvImport01")
			curves.append(thisCurve)
			
			#Get camera's near clipping plane
			shotCam = self.getCamera()
			ncp = cmds.getAttr(shotCam+".nearClipPlane")
			fl = cmds.getAttr(shotCam+".focalLength")
			
			#Create brush
			thisBrush = cmds.createNode("brush", name="rvImport_pencilBrush01")
			thisColor = self.strokeStruct[strk]['color'][0]
			cmds.setAttr(thisBrush+".color1", thisColor[0], thisColor[1], thisColor[2], type="double3")
			
			cmds.setAttr(thisBrush+".brushWidth", strkWidths[fType] * ncp * (35/fl))
			cmds.setAttr(thisBrush+".globalScale", 1.0)
			brushes.append(thisBrush)
			
			#Create controller attachment
			bcNode = cmds.createNode('blendColors', name="bc_annBrushOpacity01")
			cmds.setAttr(bcNode+".color1R", 1.0-thisColor[3])
			cmds.setAttr(bcNode+".color1G", 1.0-thisColor[3])
			cmds.setAttr(bcNode+".color1B", 1.0-thisColor[3])
			cmds.setAttr(bcNode+".color2R", 1.0)
			cmds.setAttr(bcNode+".color2G", 1.0)
			cmds.setAttr(bcNode+".color2B", 1.0)
			
			#Connect Opacity
			cmds.connectAttr(ctrlData[2]+".outputX", bcNode+".blender", f=True)
			cmds.connectAttr(bcNode+".output", thisBrush+".transparency1", f=True)
			
			#Create stroke
			thisStroke = cmds.createNode("stroke")
			strkParent = cmds.listRelatives(thisStroke, parent=True)
			strkParent = cmds.rename(strkParent[0], "rvImport_pencilStroke01")
			
			cmds.setAttr(thisStroke+".displayPercent", 100)
			cmds.setAttr(thisStroke+".pathCurve[0].samples", 200)
			strokes.append(thisStroke)
			
			#Set pressure mappings
			cmds.setAttr(thisStroke+".pressureMap1", 1)
			
			pointsNum = len(self.strokeStruct[strk]['width'])
			if not pointsNum == 1.0:
				step = 1.0 / (pointsNum-1.0)
			else:
				step = 1.0
			
			for i in range(0, pointsNum):
				thisWidth = self.strokeStruct[strk]['width'][i]
				
				#Make tips smaller
				if i == 0 or i == pointsNum-1:
					thisWidth = thisWidth * 0.75
				
				cmds.setAttr(thisStroke+".pressureScale["+str(i)+"].pressureScale_FloatValue", thisWidth)
				cmds.setAttr(thisStroke+".pressureScale["+str(i)+"].pressureScale_Position", float(i*step))
				cmds.setAttr(thisStroke+".pressureScale["+str(i)+"].pressureScale_Interp", 1)
			
			#Connect everything
			cmds.connectAttr(thisBrush+".outBrush", thisStroke+".brush", f=True)
			cmds.connectAttr(thisCurve+".worldSpace[0]", thisStroke+".pathCurve[0].curve", f=True)
			cmds.connectAttr("time1.outTime", thisBrush+".time", f=True)
			
			#Animate stroke to it's frame
			cmds.setKeyframe(strkParent, at='visibility', t=[frame-1, frame-1], v=0)
			cmds.setKeyframe(strkParent, at='visibility', t=[frame, frame], v=1)
			cmds.setKeyframe(strkParent, at='visibility', t=[frame+1, frame+1], v=0)
			
		#Group nodes
		if not cmds.objExists("|EXTRA"):
			cmds.group(em=True, name="EXTRA", w=True)
		drawGrp = cmds.group(em=True, name="rvDrawing_grp01", parent="|EXTRA")
		strokesGrp = cmds.group(strokes, name="rvStrokes_grp01", parent=drawGrp)
		offsetGrp = cmds.group(curves, name="rvOffset_grp01")
		curvesGrp = cmds.group(offsetGrp, name="rvCurves_grp01", parent=drawGrp)
		
		cmds.addAttr(drawGrp, ln="rvAnnotations", dt="string")
		cmds.setAttr(drawGrp+".rvAnnotations", "True", type="string")
		cmds.setAttr(drawGrp+".rvAnnotations", lock=True)
		
		#Create offsets and set attributes
		cmds.move(0, 0, 0, strokesGrp+".scalePivot", strokesGrp+".rotatePivot", a=True)
		cmds.move(0, 0, 0, offsetGrp+".scalePivot", offsetGrp+".rotatePivot", a=True)
		cmds.move(0, 0, 0, curvesGrp+".scalePivot", curvesGrp+".rotatePivot", a=True)
		
		#Get camera's near clipping plane
		shotCam = self.getCamera()
		ncp = cmds.getAttr(shotCam+".nearClipPlane")
		fl = cmds.getAttr(shotCam+".focalLength")
		
		if fType == "rv":
			cmds.setAttr(offsetGrp+".translateZ", -1.01 * ncp)
			cmds.setAttr(offsetGrp+".rotateX", -90)
		elif fType == "kpro":
			cmds.setAttr(offsetGrp+".translateZ", -1.01 * ncp)
			cmds.setAttr(offsetGrp+".rotateX", 90)
		
		#Position Controller
		cmds.setAttr(ctrlData[0]+".translateX", -0.2549 * ncp * (60/fl))
		cmds.setAttr(ctrlData[0]+".translateY", -0.1327 * ncp * (60/fl))
		cmds.setAttr(ctrlData[0]+".translateZ", -1.005 * ncp)
		cmds.setAttr(ctrlData[0]+".rotateX", -90)
		
		cmds.setAttr(offsetGrp+".visibility", 0)
		cmds.setAttr(offsetGrp+".overrideEnabled", 1)
		cmds.setAttr(offsetGrp+".overrideDisplayType", 2)
		cmds.setAttr(strokesGrp+".overrideEnabled", 1)
		cmds.setAttr(strokesGrp+".overrideDisplayType", 2)
		
		cmds.connectAttr(ctrlData[1]+".Visible", strokesGrp+".visibility", f=True)
		
		#Create layer for drawings
		if not "Annotations_lyr" in cmds.ls(type="displayLayer"):
			cmds.select(drawGrp, r=True)
			cmds.createDisplayLayer(name="Annotations_lyr", number=1, nr=True)
			cmds.setAttr("Annotations_lyr.color", 4)
		else:
			cmds.editDisplayLayerMembers("Annotations_lyr", drawGrp)
		
		#Remove the strokes themselves from layer
		cmds.editDisplayLayerMembers("defaultLayer", strokes, noRecurse=True)
		for stroke in strokes:
			cmds.setAttr(stroke+".overrideEnabled", 1)
			cmds.setAttr(stroke+".overrideDisplayType", 2)
		
		return {'topGRP':drawGrp,
				'strkGRP':strokesGrp,
				'offsetGRP':offsetGrp,
				'crvGRP':curvesGrp,
				'strokes':strokes,
				'curves':curves,
				'brushes':brushes
		}
	
	def interpretRV(self, rvFile):
		nodeName = ""
		strokes = []
		strokeName = ""
		strokeLines = []

		for line in rvFile:
			if line.strip() == "":
				continue

			#Interpret current line
			line = line.strip()
			if line == "{" and not self.nodeStarted:
				self.nodeStarted = True
				self.strokeStarted = False
			elif line == "{" and self.nodeStarted:
				self.nodeStarted = True
				self.strokeStarted = True
			elif line == "}" and self.strokeStarted:
				self.nodeStarted = True
				self.strokeStarted = False
			elif line == "}" and not self.strokeStarted:
				self.nodeStarted = False
				self.strokeStarted = False
			
			elif not self.nodeStarted and not self.strokeStarted:
				nodeName = line.strip()
			elif self.nodeStarted and not self.strokeStarted:
				strokeName = line.strip()
			elif self.nodeStarted and self.strokeStarted:
				strokeLines.append(line.strip())
			
			#Store date based on current state
			if len(strokeLines) > 0 and self.strokeStarted == False:
				strokes.append({strokeName: strokeLines})
				strokeLines = []
			if len(strokes) > 0 and self.nodeStarted == False:
				self.nodeStruct.append({nodeName: strokes})
				strokes = []

	def interpretKFPro(self, kfpFile):
		#Interpret Keyframe Pro
		data = json.load(kfpFile)
		
		#Rebuild kpro json into rv format
		strkIndex = 1
		thisStrokes = []
		for src in data["sources"]:
			for bkmark in src["bookmarks"]:
				thisFrm = bkmark['frame']
				if "strokes" not in bkmark:
					continue
				
				for stroke in bkmark["strokes"]:
					if stroke["type"] != 0: #not Pencil
						continue

					pointsNum = len(stroke["points"].split(";"))
					
					cHex = stroke["color"].replace("#", "")
					cRGB = tuple(int(cHex[i:i+2], 16) for i in (2, 4, 6))
					thisColor = "float[4] color = [ [ " + str(cRGB[0]/255.0)+" "+str(cRGB[1]/255.0)+" "+str(cRGB[2]/255.0) + " 1.0 ] ]"
					
					#Convert annotations to RV coordinates
					ar = cmds.getAttr("defaultResolution.deviceAspectRatio")
					pntsRV = ""
					for pnt in stroke["points"].split(";"):
						xy = pnt.split(",")
						if len(xy) <= 1:
							continue
						
						x = float(xy[0].strip()) * ar
						y = float(xy[1].strip()) / ar
						
						pntsRV += str(x)+" "+str(y)+" ] [ "
					
					thisPoints = "float[2] points = [ [ " + pntsRV + " ] ]"
					thisPoints = thisPoints.replace(' [  ]', '') #Remove empty ones
					
					thisWidth = "float width = [ "
					for _ in range(0, pointsNum):
						thisWidth += str(stroke["width"]) + " "
					thisWidth += "]"
					
					thisStrokes.append({'"pen:'+str(strkIndex)+':'+str(int(thisFrm))+':user"': [thisColor, thisPoints, thisWidth]})
					strkIndex += 1
		
		self.nodeStruct = [{'annotationsNode : RVPaint (1)':thisStrokes}]
	
	def fileInterprete(self, filename="", fType=""):
		if not os.path.isfile(filename):
			return []
		
		f = open(filename, "r")
		if fType not in ["rv", "kpro"]:
			return []
		
		func = {"rv":self.interpretRV, "kpro":self.interpretKFPro}
		func[fType](f)
		
		return self.nodeStruct
	
	def getStrokesData(self):
		if not self.nodeStruct:
			return {}
		
		for node in self.nodeStruct:
			for nodeStr in node:
				nodeParts = nodeStr.split(":")
				nodeName = nodeParts[0].strip()
				nodeType = nodeParts[1].strip().split(" ")[0]
				nodeIndex = nodeParts[1].strip().split(" ")[1]
				
				if nodeType != "RVPaint":
					continue
				
				for strokes in node[nodeStr]:
					for strokeStr in strokes:
						thisColor = []
						thisWidth = []
						thisPoints = []
						
						for line in strokes[strokeStr]:
							#Check for stroke information
							if line.startswith("float[4] color = "):
								#Interpret color data
								thisValues = line[18:-1].split("] [")
								for thisValue in thisValues:
									vals = thisValue.replace("[","").replace("]","").strip().split()
									for v in range(0, len(vals)):
										vals[v] = float(vals[v])
									
									thisColor.append(vals)
							
							elif line.startswith("float width = "):
								#Interpret width data
								thisValues = line[15:-1].strip().split()
								for v in range(0, len(thisValues)):
										thisValues[v] = float(thisValues[v])
								
								thisWidth = thisValues
								
							elif line.startswith("float[2] points = "):
								#Interpret points data
								thisValues = line[19:-1].split("] [")
								for thisValue in thisValues:
									vals = thisValue.replace("[","").replace("]","").strip().split()
									for v in range(0, len(vals)):
										vals[v] = float(vals[v])
									
									thisPoints.append(vals)
						
						#All information retrieved
						if len(thisColor) <= 0 or len(thisWidth) <= 0 or len(thisPoints) <= 0:
							continue
						
						self.strokeStruct[strokeStr] = {
								"color":thisColor,
								"width":thisWidth,
								"points":thisPoints
						}
		
		return self.strokeStruct

def show():
	global annImport_Win
	try:
		annImport_Win.close()
	except:
		pass
	annImport_Win = annImport(parent=_maya_main_window())
	mainWin = wrapInstance(long(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)