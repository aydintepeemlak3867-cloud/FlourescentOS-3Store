import sys, os, json, math, zipfile, tempfile, shutil, traceback
from pathlib import Path
from dataclasses import dataclass, asdict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QSurfaceFormat
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QTabWidget, QListWidget, QListWidgetItem, QLabel, QPushButton, QToolBar,
    QStatusBar, QFileDialog, QMessageBox, QDoubleSpinBox, QLineEdit,
    QFormLayout, QComboBox, QCheckBox, QColorDialog, QInputDialog, QMenu,
    QGroupBox, QSlider
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

try:
    from OpenGL.GL import *
    from OpenGL.GLU import gluPerspective, gluLookAt, gluProject
    OPENGL_AVAILABLE = True
except Exception:
    OPENGL_AVAILABLE = False

APP_NAME = 'Kitov Engine'
VERSION = '2.0.0'
PROJECT_FORMATS = {'.flugame': 'FluGame', '.pyapp': 'PyApp'}


def vec3(value, default=(0.0, 0.0, 0.0)):
    try:
        v = [float(x) for x in value]
        return (v + [0.0, 0.0, 0.0])[:3]
    except Exception:
        return default


@dataclass
class GameObject:
    name: str
    kind: str = 'Cube'
    position: tuple = (0.0, 0.0, 0.0)
    rotation: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)
    color: str = '#7da7d9'
    visible: bool = True
    tag: str = 'Untagged'

    def to_dict(self):
        d = asdict(self)
        for k in ('position', 'rotation', 'scale'):
            d[k] = list(d[k])
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=str(d.get('name', 'GameObject')), kind=str(d.get('kind', 'Cube')),
            position=vec3(d.get('position')), rotation=vec3(d.get('rotation')),
            scale=vec3(d.get('scale'), (1, 1, 1)), color=str(d.get('color', '#7da7d9')),
            visible=bool(d.get('visible', True)), tag=str(d.get('tag', 'Untagged'))
        )


class Scene:
    def __init__(self):
        self.objects = [
            GameObject('Main Camera', 'Camera', (0, 2, 7), tag='MainCamera'),
            GameObject('Directional Light', 'Light', (2, 5, 2), color='#fff1c1'),
            GameObject('Cube', 'Cube', (0, 0.5, 0), color='#4e9ad6'),
            GameObject('Ground', 'Plane', (0, -0.55, 0), scale=(8, 1, 8), color='#596b55', tag='Environment')
        ]

    def add(self, kind, name=None):
        counts = sum(1 for o in self.objects if o.kind == kind)
        obj = GameObject(name or f'{kind}_{counts + 1}', kind)
        if kind == 'Sphere': obj.color = '#d69a4e'
        if kind == 'Plane': obj.color = '#596b55'; obj.scale = (4, 1, 4)
        if kind == 'Light': obj.color = '#fff1c1'
        self.objects.append(obj)
        return obj

    def serialize(self):
        return {'schema': 1, 'engine': APP_NAME, 'version': VERSION,
                'objects': [o.to_dict() for o in self.objects],
                'settings': {'clear_color': '#20242b', 'camera_fov': 55}}

    @classmethod
    def deserialize(cls, data):
        s = cls()
        s.objects = [GameObject.from_dict(x) for x in data.get('objects', [])]
        return s


class Viewport(QOpenGLWidget):
    objectPicked = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.selected = -1
        self.yaw, self.pitch, self.distance = 35.0, 22.0, 10.0
        self.target = [0.0, 0.0, 0.0]
        self.last_mouse = None
        self.orbiting = False
        self.show_grid = True
        self.wireframe = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 300)

    def initializeGL(self):
        if not OPENGL_AVAILABLE: return
        glEnable(GL_DEPTH_TEST); glEnable(GL_CULL_FACE); glCullFace(GL_BACK)
        glEnable(GL_COLOR_MATERIAL); glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glClearColor(0.10, 0.12, 0.15, 1.0)

    def resizeGL(self, w, h):
        if not OPENGL_AVAILABLE: return
        glViewport(0, 0, max(1, w), max(1, h))
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(55.0, max(1, w) / max(1, h), 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)

    def camera_position(self):
        y = math.radians(self.yaw); p = math.radians(self.pitch)
        return (self.target[0] + self.distance * math.cos(p) * math.sin(y),
                self.target[1] + self.distance * math.sin(p),
                self.target[2] + self.distance * math.cos(p) * math.cos(y))

    def paintGL(self):
        if not OPENGL_AVAILABLE:
            return
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        eye = self.camera_position()
        gluLookAt(*eye, *self.target, 0, 1, 0)
        if self.show_grid: self.draw_grid()
        if not self.scene: return
        for i, obj in enumerate(self.scene.objects):
            if not obj.visible or obj.kind in ('Camera', 'Light'): continue
            self.draw_object(obj, i == self.selected)

    def draw_grid(self):
        glDisable(GL_LIGHTING); glLineWidth(1.0); glBegin(GL_LINES)
        for i in range(-20, 21):
            shade = 0.28 if i == 0 else 0.18
            glColor3f(shade, shade, shade)
            glVertex3f(i, -0.51, -20); glVertex3f(i, -0.51, 20)
            glVertex3f(-20, -0.51, i); glVertex3f(20, -0.51, i)
        glEnd()
        glBegin(GL_LINES)
        glColor3f(.75,.22,.22); glVertex3f(-20,-.5,0); glVertex3f(20,-.5,0)
        glColor3f(.22,.65,.28); glVertex3f(0,-.5,-20); glVertex3f(0,-.5,20)
        glEnd()

    def draw_object(self, obj, selected=False):
        c = QColor(obj.color)
        glPushMatrix()
        glTranslatef(*obj.position)
        glRotatef(obj.rotation[0], 1, 0, 0); glRotatef(obj.rotation[1], 0, 1, 0); glRotatef(obj.rotation[2], 0, 0, 1)
        glScalef(*obj.scale)
        if selected:
            glDisable(GL_LIGHTING); glPolygonMode(GL_FRONT_AND_BACK, GL_LINE); glLineWidth(2.2)
            glColor3f(1.0, .75, .15); self.geometry(obj.kind)
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL); glLineWidth(1.0)
        glColor3f(c.redF(), c.greenF(), c.blueF())
        if self.wireframe: glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        self.geometry(obj.kind)
        if self.wireframe: glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glPopMatrix()

    def geometry(self, kind):
        if kind == 'Sphere': self.sphere()
        elif kind == 'Plane': self.cube()
        else: self.cube()

    def cube(self):
        faces = [((0,0,1),[(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)]),
                 ((0,0,-1),[(.5,-.5,-.5),(-.5,-.5,-.5),(-.5,.5,-.5),(.5,.5,-.5)]),
                 ((1,0,0),[(.5,-.5,.5),(.5,-.5,-.5),(.5,.5,-.5),(.5,.5,.5)]),
                 ((-1,0,0),[(-.5,-.5,-.5),(-.5,-.5,.5),(-.5,.5,.5),(-.5,.5,-.5)]),
                 ((0,1,0),[(-.5,.5,.5),(.5,.5,.5),(.5,.5,-.5),(-.5,.5,-.5)]),
                 ((0,-1,0),[(-.5,-.5,-.5),(.5,-.5,-.5),(.5,-.5,.5),(-.5,-.5,.5)])]
        glBegin(GL_QUADS)
        for normal, verts in faces:
            glNormal3f(*normal)
            for v in verts: glVertex3f(*v)
        glEnd()

    def sphere(self):
        slices, stacks = 20, 14
        for j in range(stacks):
            lat0 = math.pi * (-.5 + j / stacks); lat1 = math.pi * (-.5 + (j+1) / stacks)
            glBegin(GL_QUAD_STRIP)
            for i in range(slices + 1):
                lon = 2 * math.pi * i / slices
                for lat in (lat0, lat1):
                    x, y, z = math.cos(lat)*math.cos(lon), math.sin(lat), math.cos(lat)*math.sin(lon)
                    glNormal3f(x,y,z); glVertex3f(x*.5,y*.5,z*.5)
            glEnd()

    def mousePressEvent(self, e):
        self.last_mouse = e.position().toPoint()
        if e.button() == Qt.MouseButton.RightButton: self.orbiting = True
        elif e.button() == Qt.MouseButton.LeftButton: self.pick(e.position().x(), e.position().y())

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self.last_mouse and self.orbiting:
            delta = pos - self.last_mouse
            self.yaw += delta.x() * .55; self.pitch = max(-89, min(89, self.pitch + delta.y() * .45))
            self.update()
        self.last_mouse = pos

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton: self.orbiting = False

    def wheelEvent(self, e):
        self.distance = max(1.5, min(100, self.distance * (0.88 if e.angleDelta().y() > 0 else 1.14)))
        self.update()

    def pick(self, x, y):
        if not self.scene: return
        # Screen-space center picking with a forgiving radius; nearest projected object wins.
        best, best_d = -1, 32.0
        for i, obj in enumerate(self.scene.objects):
            if obj.kind in ('Camera', 'Light') or not obj.visible: continue
            sx, sy, _ = self.project(obj.position)
            d = math.hypot(sx - x, sy - y)
            if d < best_d: best, best_d = i, d
        if best >= 0: self.objectPicked.emit(best)

    def project(self, pos):
        if not OPENGL_AVAILABLE: return (0, 0, 0)
        self.makeCurrent()
        model = glGetDoublev(GL_MODELVIEW_MATRIX); proj = glGetDoublev(GL_PROJECTION_MATRIX); vp = glGetIntegerv(GL_VIEWPORT)
        return gluProject(pos[0], pos[1], pos[2], model, proj, vp)[:2][0], self.height() - gluProject(pos[0], pos[1], pos[2], model, proj, vp)[1], 0


class Inspector(QWidget):
    changed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent); self.obj = None; self._loading = False
        root = QVBoxLayout(self); root.setContentsMargins(8,8,8,8)
        self.name = QLineEdit(); self.active = QCheckBox('Visible / Active'); self.tag = QLineEdit()
        form = QFormLayout(); form.addRow('Name', self.name); form.addRow('', self.active); form.addRow('Tag', self.tag)
        root.addLayout(form)
        self.spins = {}
        for key, title, defaults in [('position','Position',(0,0,0)),('rotation','Rotation',(0,0,0)),('scale','Scale',(1,1,1))]:
            box = QGroupBox(title); row = QHBoxLayout(box)
            for axis, default in zip('XYZ', defaults):
                s = QDoubleSpinBox(); s.setRange(-100000,100000); s.setDecimals(3); s.setSingleStep(.1); s.setValue(default); s.setPrefix(axis+' '); s.setMinimumWidth(86)
                self.spins[(key,axis)] = s; row.addWidget(s); s.valueChanged.connect(self.apply)
            root.addWidget(box)
        self.kind = QLabel('Type: —'); root.addWidget(self.kind)
        color_row = QHBoxLayout(); self.color_btn = QPushButton('Material Color…'); color_row.addWidget(self.color_btn); root.addLayout(color_row)
        self.color_btn.clicked.connect(self.choose_color)
        self.name.editingFinished.connect(self.apply); self.tag.editingFinished.connect(self.apply); self.active.toggled.connect(self.apply)
        root.addStretch()

    def set_object(self, obj):
        self._loading = True; self.obj = obj
        enabled = obj is not None
        for w in [self.name,self.active,self.tag,self.color_btn,*self.spins.values()]: w.setEnabled(enabled)
        if obj:
            self.name.setText(obj.name); self.active.setChecked(obj.visible); self.tag.setText(obj.tag); self.kind.setText('Type: '+obj.kind)
            for key in ('position','rotation','scale'):
                for axis, val in zip('XYZ', getattr(obj,key)): self.spins[(key,axis)].setValue(val)
        else:
            self.name.clear(); self.tag.clear(); self.kind.setText('Type: —')
        self._loading = False

    def apply(self, *args):
        if self._loading or not self.obj: return
        self.obj.name = self.name.text().strip() or self.obj.name; self.obj.tag = self.tag.text(); self.obj.visible = self.active.isChecked()
        for key in ('position','rotation','scale'):
            setattr(self.obj, key, tuple(self.spins[(key,a)].value() for a in 'XYZ'))
        self.changed.emit()

    def choose_color(self):
        if not self.obj: return
        c = QColorDialog.getColor(QColor(self.obj.color), self, 'Material Color')
        if c.isValid(): self.obj.color = c.name(); self.changed.emit()


class KitovEngine(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f'{APP_NAME} {VERSION} — 3D Game Studio'); self.resize(1500, 900)
        self.scene = Scene(); self.selected = -1; self.project_path = ''; self.project_name = 'Untitled_Project'
        self.playing = False; self.saved_snapshot = None
        self.setStyleSheet('''QMainWindow,QWidget{background:#1e1e1e;color:#d4d4d4;font-family:Segoe UI} QMenuBar,QToolBar{background:#2d2d2d;color:#ddd;border:0;spacing:6px} QMenu{background:#252526;color:#ddd} QMenu::item:selected{background:#094771} QPushButton{background:#333;border:1px solid #505050;border-radius:4px;padding:6px 10px;color:#eee} QPushButton:hover{border-color:#168bd2;background:#3b3b3b} QLineEdit,QDoubleSpinBox,QComboBox,QListWidget{background:#181818;border:1px solid #444;padding:4px;color:#ddd} QTabWidget::pane{border:1px solid #444} QStatusBar{background:#0875ad;color:white} QGroupBox{border:1px solid #444;border-radius:5px;margin-top:8px;padding-top:8px;color:#70c6b5}''')
        self._build_ui(); self._build_menus(); self.refresh_hierarchy(); self.select_object(2)
        self.timer = QTimer(self); self.timer.timeout.connect(self.game_tick); self.timer.start(16)

    def _build_ui(self):
        bar = QToolBar('Main'); bar.setMovable(False); self.addToolBar(bar)
        self.play_btn = QPushButton('▶ Play'); self.play_btn.clicked.connect(self.toggle_play); bar.addWidget(self.play_btn)
        stop = QPushButton('■ Stop'); stop.clicked.connect(self.stop_play); bar.addWidget(stop)
        bar.addSeparator()
        for label, kind in [('＋ Cube','Cube'),('＋ Sphere','Sphere'),('＋ Plane','Plane'),('＋ Empty','Empty'),('＋ Light','Light')]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,k=kind:self.add_object(k)); bar.addWidget(b)
        bar.addSeparator(); self.mode = QComboBox(); self.mode.addItems(['Scene View','Game Preview']); self.mode.currentIndexChanged.connect(self.change_view); bar.addWidget(self.mode)
        central=QWidget(); layout=QHBoxLayout(central); layout.setContentsMargins(4,4,4,4)
        split=QSplitter(Qt.Orientation.Horizontal)
        left=QTabWidget(); self.hierarchy=QListWidget(); self.hierarchy.currentRowChanged.connect(self.select_object); left.addTab(self.hierarchy,'Hierarchy')
        self.assets=QListWidget(); self.assets.addItems(['Scenes/','Scripts/','Textures/','Materials/','Audio/','Prefabs/']); left.addTab(self.assets,'Project')
        split.addWidget(left)
        mid=QSplitter(Qt.Orientation.Vertical); self.viewport=Viewport(); self.viewport.scene=self.scene; self.viewport.objectPicked.connect(self.select_object); mid.addWidget(self.viewport)
        self.console=QListWidget(); self.console.addItem('Kitov Engine 2.0 initialized. OpenGL viewport ready.'); mid.addWidget(self.console); mid.setSizes([650,180]); split.addWidget(mid)
        self.inspector=Inspector(); self.inspector.changed.connect(self.refresh_view); split.addWidget(self.inspector)
        split.setSizes([250,950,320]); layout.addWidget(split); self.setCentralWidget(central)
        self.status=QStatusBar(); self.setStatusBar(self.status); self.status.showMessage('Ready | Scene View | Right-drag: orbit · Wheel: zoom · Left-click: select')

    def _build_menus(self):
        fm=self.menuBar().addMenu('File')
        for label, fn, shortcut in [('New Project',self.new_project,'Ctrl+N'),('Open Project…',self.open_project,'Ctrl+O'),('Save Project',self.save_project,'Ctrl+S'),('Save Project As…',self.save_as,''),('Export PyApp…',lambda:self.save_as('.PyApp'),''),('Quit',self.close,'Ctrl+Q')]:
            a=QAction(label,self); a.triggered.connect(fn)
            if shortcut:a.setShortcut(shortcut)
            fm.addAction(a)
        om=self.menuBar().addMenu('GameObject')
        for kind in ('Cube','Sphere','Plane','Empty','Light','Camera'):
            a=QAction('Create '+kind,self); a.triggered.connect(lambda checked=False,k=kind:self.add_object(k)); om.addAction(a)
        em=self.menuBar().addMenu('Edit'); delete=QAction('Delete Selected',self); delete.setShortcut('Delete'); delete.triggered.connect(self.delete_selected); em.addAction(delete)
        vm=self.menuBar().addMenu('View'); grid=QAction('Show Grid',self,checkable=True); grid.setChecked(True); grid.toggled.connect(self.toggle_grid); vm.addAction(grid)
        wire=QAction('Wireframe',self,checkable=True); wire.toggled.connect(self.toggle_wire); vm.addAction(wire)

    def log(self, msg): self.console.addItem(msg); self.console.scrollToBottom()
    def refresh_hierarchy(self):
        self.hierarchy.blockSignals(True); self.hierarchy.clear()
        for o in self.scene.objects:
            item=QListWidgetItem(('◉ ' if o.visible else '○ ')+o.name+'  ['+o.kind+']'); self.hierarchy.addItem(item)
        if 0 <= self.selected < len(self.scene.objects): self.hierarchy.setCurrentRow(self.selected)
        self.hierarchy.blockSignals(False)

    def select_object(self, index):
        self.selected=index if 0 <= index < len(self.scene.objects) else -1
        self.inspector.set_object(self.scene.objects[self.selected] if self.selected >= 0 else None)
        self.viewport.selected=self.selected; self.viewport.update(); self.refresh_hierarchy()

    def refresh_view(self): self.refresh_hierarchy(); self.viewport.update()
    def add_object(self, kind):
        obj=self.scene.add(kind); self.selected=len(self.scene.objects)-1; self.refresh_hierarchy(); self.select_object(self.selected); self.log(f'Created {obj.kind}: {obj.name}')
    def delete_selected(self):
        if self.selected < 0:return
        obj=self.scene.objects.pop(self.selected); self.selected=-1; self.refresh_hierarchy(); self.select_object(-1); self.log('Deleted '+obj.name)
    def toggle_grid(self, v): self.viewport.show_grid=v; self.viewport.update()
    def toggle_wire(self, v): self.viewport.wireframe=v; self.viewport.update()
    def change_view(self, index):
        self.status.showMessage('Scene editing enabled' if index==0 else 'Game preview — camera view'); self.viewport.update()

    def toggle_play(self):
        if not self.playing:
            self.saved_snapshot=self.scene.serialize(); self.playing=True; self.play_btn.setText('Ⅱ Pause'); self.log('Play mode started.')
        else:
            self.playing=False; self.play_btn.setText('▶ Play'); self.log('Play mode paused.')
    def stop_play(self):
        if self.saved_snapshot:
            self.scene=Scene.deserialize(self.saved_snapshot); self.viewport.scene=self.scene; self.saved_snapshot=None
        self.playing=False; self.play_btn.setText('▶ Play'); self.refresh_hierarchy(); self.select_object(-1); self.viewport.update(); self.log('Play mode stopped; scene restored.')
    def game_tick(self):
        if self.playing:
            # Small deterministic runtime update hook; scripts/components can extend this loop.
            self.viewport.update()

    def new_project(self):
        if QMessageBox.question(self,'New Project','Create a new project? Unsaved changes will be lost.') != QMessageBox.StandardButton.Yes:return
        self.scene=Scene(); self.viewport.scene=self.scene; self.project_path=''; self.project_name='Untitled_Project'; self.selected=-1; self.refresh_hierarchy(); self.select_object(2); self.log('New project created.')

    def project_data(self): return {'format':'KitovProject','version':VERSION,'name':self.project_name,'scene':self.scene.serialize()}
    def save_project(self):
        if not self.project_path:return self.save_as()
        return self._write_project(self.project_path)
    def save_as(self, forced_ext=None):
        ext=forced_ext or '.FluGame'; path, _=QFileDialog.getSaveFileName(self,'Save Kitov Project',self.project_name+ext,'Kitov Projects (*.FluGame *.PyApp)')
        if not path:return
        if Path(path).suffix.lower() not in PROJECT_FORMATS:path+=ext
        self.project_path=path; self.project_name=Path(path).stem; self._write_project(path)
    def _write_project(self,path):
        data=self.project_data(); manifest=json.dumps(data,ensure_ascii=False,indent=2)
        try:
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('project.json',manifest)
                z.writestr('README.txt',f'{APP_NAME} {VERSION}\nProject: {self.project_name}\nOpen this file with Kitov Engine.\n')
                if Path(path).suffix.lower()=='.pyapp':
                    # .PyApp is a portable Kitov application-project container, not a fake standalone executable.
                    z.writestr('manifest.json',json.dumps({'type':'Kitov PyApp Project','engine_version':VERSION,'main_scene':'project.json'},indent=2))
            self.status.showMessage('Saved: '+path,5000); self.log('Project saved: '+path); return True
        except Exception as e: QMessageBox.critical(self,'Save failed',str(e)); return False

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Open Kitov Project','','Kitov Projects (*.FluGame *.PyApp *.zip)')
        if not path:return
        try:
            with zipfile.ZipFile(path,'r') as z: data=json.loads(z.read('project.json').decode('utf-8'))
            self.scene=Scene.deserialize(data['scene']); self.viewport.scene=self.scene; self.project_path=path; self.project_name=data.get('name',Path(path).stem)
            self.selected=-1; self.refresh_hierarchy(); self.select_object(-1); self.viewport.update(); self.log('Opened project: '+path); self.status.showMessage('Loaded '+self.project_name)
        except Exception as e: QMessageBox.critical(self,'Open failed',f'Could not load project:\n{e}')


def main():
    if not OPENGL_AVAILABLE:
        app=QApplication(sys.argv)
        QMessageBox.critical(None,'Kitov Engine — Missing dependency','3D rendering requires PyOpenGL.\n\nInstall dependencies with:\npython -m pip install PyQt6 PyOpenGL PyOpenGL_accelerate')
        return 2
    fmt=QSurfaceFormat(); fmt.setDepthBufferSize(24); fmt.setVersion(2,1); fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile); QSurfaceFormat.setDefaultFormat(fmt)
    app=QApplication(sys.argv); app.setStyle('Fusion'); win=KitovEngine(); win.show(); return app.exec()

if __name__=='__main__':
    sys.exit(main())
