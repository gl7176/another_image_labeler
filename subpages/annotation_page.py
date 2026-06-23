import math, json, os, datetime, glob, numpy as np, colorsys
from nicegui import ui, events, app
from pathlib import Path
from PIL import Image
#import Maritimelapse

### Section for color handling (drawing boxes, etc.)

colors = {'default': 'red',
          'selected': 'yellow',
          'active': 'black',
          'selecting': 'white'}

def number_to_color(i):
    golden_angle = 137.5 / 360.0
    h = (i * golden_angle) % 1.0
    s = 0.7 
    v = 0.9 
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    r, g, b = int(r*255), int(g*255), int(b*255)
    return f"#{r:02x}{g:02x}{b:02x}"


def gen_palette(x):
    return [number_to_color(i) for i in range(0, x)]


### Section for handling annotation boxes and returning SVG code on call

class AnnotationRectangle:
    """
    The rectangle that gets loaded when you click on the SVG
    which we'll use to replace/update/correct/revise the existing record and drawing
    """

    def __init__(self, x1, y1, w=None, h=None, x2=None, y2=None, label="default",
                 source="manually annotated", description=None) -> None:
        self.timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')
        self.source = f'Source: {source} [{self.timestamp}]'
        self.label = label
        
        if description == None: self.description = self.source
        elif "Source" not in description: self.description = "; ".join([self.source, description])
        else: self.description = description

        if x2 != None and w == None: self.x1, self.x2, self.width = min(x1, x2), max(x1, x2), max(x1, x2) - min(x1, x2)
        elif x2 == None and w != None: self.x1, self.x2, self.width = min(x1, x1+w), max(x1, x1+w), w
        elif x2 != None and w != None and x1+w != x2: raise ValueError("The width given does not match difference between X coordinates provided")
        else: self.x1, self.x2, self.width = min(x1, x2), max(x1, x2), w
        
        if y2 != None and h == None: self.y1, self.y2, self.height = min(y1, y2), max(y1, y2), max(y1, y2) - min(y1, y2)
        elif y2 == None and h != None: self.y1, self.y2, self.height = min(y1, y1+h), max(y1, y1+h), h
        elif y2 != None and h != None and y1+h != y2: raise ValueError("The height given does not match difference between Y coordinates provided")
        else: self.y1, self.y2, self.height = min(y1, y2), max(y1, y2), h

    def _as_SVG(self, box_fill = "none", box_color=colors['default'], box_strength = 2, additional_params = None, with_label=False):
        shape = f'''
                <rect x="{self.x1}" y="{self.y1}" width="{self.width}" height="{self.height}" 
                    style="fill:{box_fill};stroke:{box_color};stroke-width:{box_strength}"{f'; {additional_params}' if additional_params != None else ""}" />
                '''
        font_size = 20
        label = f'''
                    <text x="{(self.x1)}" y="{self.y2+font_size}" fill="{box_color}" font-size="{font_size}" font-weight="bold">{self.label}</text>
                    '''
        if with_label:
            return shape + " " + label
        
        else:
            return shape

    def _as_JSON(self):
        return {
            'label': self.label, 
            'points': [[self.x1, self.y1],
            [self.x2, self.y2]],
            'group_id': None,
            'description': self.description,
            'shape_type': 'rectangle',
            'flags': {},
            'mask': None
           }
        
### A class to pass mouse behavior between the page frame and the working image object

class DummyMouse:
    def __init__(self, action, x, y):
        self.type = action
        self.button = 0
        self.image_x, self.image_y = x,y

### A class to contain the working image object within the page frame
### Heavily adapted from examples in https://nicegui.io/documentation/interactive_image

class WorkingImage:
    """
    Class for an image that's getting annotated
    """
    
    def __init__(self, focal_image, show_annotations=False) -> None:
        ui.keyboard(self._handle_key)
        self.src = focal_image
        self.imdims = Image.open(self.src).size
        self.jpath = Path(self.src).parent / f'{str(Path(self.src).stem)}.json'
        try: self.load_classes_file()
        except: self.classes = []
        try: self.load_annotations_file()
        except: self.annotations = []
        self.show_anns = show_annotations
        self.show_labels = False
        self.start_x, self.start_y = 0, 0
        self.is_dragging = False
        self.mode = "drawing"
        self.selected_annotations = []
        self.active_annotations = []
        # sets to the majority class
        self._initialize_classes()
        self.palette = gen_palette(len(self.classes))
        self.save_flag = False

    def _initialize_classes(self):
        #if self.annotations != []: # if there are annotations, get a tally, append any new ones to list, set active to majority
        class_counts = np.unique([box.label for box in self.annotations], return_counts=True)
        [self.classes.append(label) for label in class_counts[0] if label not in self.classes]
        if self.classes == []: self.classes.append('unclassified')
        if len(class_counts[0]) > 1:
            self.active_class = class_counts[0][class_counts[1]==max(class_counts[1])]
        else: self.active_class = self.classes[0]
        
    
    ### The following functions are assigned to hotkeys in the function _handle_key
    ### (though they may be called beyond that)
    
    def _toggle_labels(self):
        self.show_labels = not self.show_labels
        ui.notify(f'Labels {'on' if self.show_labels else 'off'}')
        self._draw_annotations()
    
    def _toggle_annotations(self):
        self.show_anns = not self.show_anns
        self._draw_annotations()
        ui.notify(f'Annotations {"visible" if self.show_anns else "hidden"}')

    def _clear_new_annotations(self):
        self.annotations = []
        if os.path.exists(self.jpath):
            self.load_annotations_file()
        self.ii.content=self._compile_SVGs()
        ui.notify("Clearing new annotations")
        self.save_flag = False

    def _save_annotations_and_classes(self):
        if len(self.annotations) > 0:
            if os.path.isfile(self.jpath):
                self._archive_JSON(self.jpath)
            self._export_JSON([box._as_JSON() for box in self.annotations])
            print(f'exporting {len(self.annotations)} annotations')
        else: print('No annotations to export')
        if len(self.classes) > 0:
            with open(Path(self.src).parent / 'classes.txt', 'w') as f:
                for item in self.classes:
                    f.write(f"{item}\n")
            print(f'Classes exported to {str(Path(self.src).parent / 'classes.txt')}')
        else: print('No annotations to export')
        self.save_flag = False
        
    def _toggle_edit_mode(self):
        if self.mode == 'editing':
            try: self.clear_editing()
            except: pass
            self.mode = 'drawing'
            ui.notify("Drawing mode", props={'no_focus': True})       
            self.selected_annotations = []
        else:
            self.mode = 'editing'
            self.show_anns = True
            ui.notify("Editing mode", props={'no_focus': True})
        self.ii.content=self._compile_SVGs()

    def _delete_annotations(self):
        if self.mode=='editing' and self.active_annotations != 0:
            for i in sorted(self.active_annotations, reverse=True):
                del self.annotations[i]
            self._clear_editing()
        if self.mode=='drawing':
            try:
                del self.annotations[-1]
                self._draw_annotations()
            except: pass

    def _clear_editing(self):
        self.selected_annotations = []
        self.active_annotations = []
        self.editing_layer.content = ""
        self._draw_annotations()

    def _select_all_annotations(self):
        if self.mode == 'editing':
            self.selected_annotations = self.active_annotations = range(0, len(self.annotations))
            self.editing_layer.content = f'{" ".join([box._as_SVG(box_color=colors['active'], box_strength = 8, additional_params = "stroke-dasharray='8 4'") for box in [self.annotations[i] for i in self.selected_annotations]])} {" ".join([box._as_SVG(box_color=colors['selected'], box_strength = 2) for box in [self.annotations[i] for i in self.selected_annotations]])}'
    
    ### Function that delegates functions in response to hotkeys
    ### Could redesign this to pass arguments from outer keyboard handling
    def _handle_key(self, e: events.KeyEventArguments) -> None:
        if e.key.escape: ui.navigate.to('/gallery')
        if e.key == 'a' and not e.modifiers.ctrl and not e.action.repeat and e.action.keydown: self._toggle_annotations()
        if e.key == 'a' and e.modifiers.ctrl and not e.action.repeat and e.action.keydown: self._select_all_annotations()
        if e.key == 'a' and not e.modifiers.ctrl and not e.action.repeat and e.action.keydown: pass #self._select_all_ann
        if e.key == "p" and e.action.keydown: print('diagnostics placeholder')
        if e.key == 'c' and e.action.keydown: self._clear_new_annotations()
        if e.key == 'l' and e.action.keydown: self._toggle_labels()
        if e.key == 's' and not e.action.repeat and e.action.keydown: self._save_annotations_and_classes()
        if e.key == 'n' and e.action.keydown: self.new_function() # new function placeholder
        if e.key == 'e' and e.action.keydown: self._toggle_edit_mode()
        if e.key == 'p' and e.action.keydown: ui.notify(self.src)
        if (e.key == 'Delete' or e.key == "d") and e.action.keydown: self._delete_annotations()

    def new_function(self):
        ui.notify("Oh god how did this get here I am not good with computer")

    def _compile_SVGs(self, additional_params=None, with_label=False):
        if self.mode == "editing" and len(self.selected_annotations) != 1: additional_params = 'pointer-events="all" cursor="pointer"'
        if self.show_labels: with_label=True
        if len(self.annotations) > 0:
            return " ".join([box._as_SVG(box_color=self.palette[self.classes.index(box.label)], additional_params=additional_params, with_label=with_label) for box in self.annotations])
        else: return ""

    def _export_JSON(self, data, outname = "default"):
        outpath = self.jpath
        print(f'Annotations saved to: {outpath}')
        data = {'version': 'not logged', 'flags': {}, 'shapes':data,
                'imagePath': Path(self.src).name, 'imageData': None,
                'imageHeight': self.imdims[1], 'imageWidth': self.imdims[0]}
        with open(outpath, "w") as file:
            json.dump(data, file, indent=2)
        ui.notify('Annotations exported')

    def _archive_JSON(self, json_path):
        newname = str(json_path).replace('.json', f'-{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S')}.json')
        os.rename(json_path, newname)
    
    def _draw_annotations(self):
        if self.show_anns: self.ii.content=self._compile_SVGs()
        else: self.ii.content="" 
        if self.annotations == []: ui.notify('(no annotations present yet)')



    ### The following function activates the core behavior of the interactive image
    
    def initialize_image(self) -> ui.interactive_image:

        ### Drawing boxes in "drawing mode"
        ### largely informed by the clicking and overlay examples online
        ### https://nicegui.io/documentation/interactive_image specifically "adding layers" and "SVG overlay"
        
        def box_drawing(e):
            self.editing_layer.content = ""
            if e.type == 'mousedown' and e.button == 0:
                self.is_dragging, self.start_x, self.start_y = True, e.image_x, e.image_y
                if self.classes == []:
                    self.classes.append(self.active_class)
                    self.palette.append(number_to_color(0))
            elif e.type == 'mousemove' and self.is_dragging:
                w, h = e.image_x - self.start_x, e.image_y - self.start_y
                if self.show_anns: self.ii.content = self._compile_SVGs()
                else: self.ii.content = ""
                self.ii.content = self.ii.content + AnnotationRectangle(min(self.start_x, e.image_x), min(self.start_y, e.image_y), w=abs(w), h=abs(h))._as_SVG(box_color=self.palette[self.classes.index(self.active_class)], box_fill='rgba(255,255,0,0.3)')
                
            elif (e.type == 'mouseup' or e.type == 'mouseleave') and e.button == 0 and self.is_dragging:
                self.is_dragging, w, h = False, abs(e.image_x - self.start_x), abs(e.image_y - self.start_y)
                if w > 5 and h > 5:  # Avoid creating tiny boxes
                    self.annotations.append(
                        AnnotationRectangle(min(self.start_x, e.image_x), min(self.start_y, e.image_y), w=w, h=h, label=self.active_class)
                    )
                    self.save_flag = True
                if self.show_anns: self.ii.content = self._compile_SVGs()
                else: aui.notify("Annotations currently hidden")


        ### Selecting boxes in "editing mode"
        
        def box_selecting_and_editing(e):
            if e.type == 'mousedown' and e.button == 0:
                self.editing_layer.content = ""
                self.is_dragging, self.start_x, self.start_y = True, e.image_x, e.image_y
            elif e.type == 'mousemove' and self.is_dragging:
                w, h = e.image_x - self.start_x, e.image_y - self.start_y
                self.ii.content = self._compile_SVGs() + AnnotationRectangle(min(self.start_x, e.image_x), min(self.start_y, e.image_y), w=abs(w), h=abs(h))._as_SVG(box_color=colors['selecting'], box_fill='rgba(235,235,235,0.3)')
                if e.image_x==0 or e.image_y==0 or e.image_x==self.imdims[0] or e.image_y==self.imdims[1]:
                    e.type='mouseup'
            elif (e.type == 'mouseup') and e.button == 0 and self.is_dragging:
                self.is_dragging = False
                x1, x2, y1, y2 = min(e.image_x, self.start_x), max(e.image_x, self.start_x), min(e.image_y, self.start_y), max(e.image_y, self.start_y)
                self.selected_annotations = [self.annotations.index(box) for box in self.annotations if (box.x2 > x1 and
                                                                                                     box.y2 > y1 and
                                                                                                     box.x1 < x2 and
                                                                                                     box.y1 < y2)]
                self.active_annotations = self.selected_annotations
                self.ii.content = self._compile_SVGs()
                self.editing_layer.content = f'{" ".join([box._as_SVG(box_color=colors['selected'], box_strength = 2) for box in [self.annotations[i] for i in self.selected_annotations]])} {" ".join([box._as_SVG(box_color=colors['active'], box_strength = 8, additional_params = "stroke-dasharray='8 4'") for box in [self.annotations[i] for i in self.selected_annotations]])}'


        ### Reading mouse behavior and mode and passing to the appropriate function
        
        def mouse_handler(e: events.MouseEventArguments):
            if self.classes == []:
                ui.notify('No classes yet: press O then enter a class to start annotating')
                return
            if self.mode == 'drawing':
                box_drawing(e)
                self.editing_layer.content = ""
            if self.show_anns and self.mode == 'editing':
                box_selecting_and_editing(e)

        ### receive mouse behavior from page frame, feed it into the interactive image
        def box_drag_passthrough(e, action):
            m = DummyMouse(action=action, x=e.args['image_x'], y=e.args['image_y'])
            box_selecting_and_editing(m)

        ### clicking to select/deselect a box
        def select_single_box(clicked):
            if clicked == self.selected_annotations:
                self.selected_annotations = []
                self.active_annotations = []            
            else:
                self.selected_annotations = clicked
                self.active_annotations = clicked
        
        ### special handling for when a click selects overlapping boxes
        def select_multi_box(clicked):
            ui.notify('Multiple boxes clicked, cycling through them')
            self.selected_annotations = clicked
            if self.active_annotations == []: self.active_annotations = [self.selected_annotations[0]]
            elif self.active_annotations != [] and set(self.active_annotations).issubset(set(clicked)):
                x = [i for i in clicked if i != self.active_annotations[0]]
                self.active_annotations = [x[clicked.index(self.active_annotations[0]) % len(x)]]
            elif self.selected_annotations == clicked:
                self.active_annotations = [self.selected_annotations[0]]

        ### parent function for selecting any box(es)
        def select_annotation(e):
            self.editing_layer.content = ""
            print(f'Select box here! Select  annotation box under {e.args['image_x'], e.args['image_y']}')
            clicked=[count for count, box in enumerate(self.annotations) if box.x1 < e.args['image_x'] < box.x2 and box.y1 < e.args['image_y'] < box.y2]
            if len(clicked) == 1: select_single_box(clicked)
            elif len(clicked) > 1: select_multi_box(clicked)
            self.editing_layer.content = " ".join([box._as_SVG(box_color=colors['selected'], box_strength = 2) for box in [self.annotations[i] for i in self.selected_annotations]])
            print(f'active annotation: {self.active_annotations}')
            if len(clicked) >0: self.editing_layer.content = self.annotations[self.active_annotations[0]]._as_SVG(box_color=colors['active'], box_strength = 8, additional_params = "stroke-dasharray='8 4'") + self.editing_layer.content

        ### the actual step of creating the interactive image, with all dependent triggers and functions
        self.ii = ui.interactive_image(
            self.src, on_mouse=mouse_handler, events=['mousedown', 'mouseup', 'mousemove', 'mouseleave'], cross=True, sanitize=False).on('svg:pointerdown', lambda e: select_annotation(e)).on('svg:pointermove', lambda e: box_drag_passthrough(e, action='mousemove')).on('svg:pointerup', lambda e: box_drag_passthrough(e, action='mouseup'))
        self.editing_layer = self.ii.add_layer()

        if self.show_anns: self._draw_annotations()

    ### function for loading annotations from a file
    def load_annotations_file(self):
        self.annotations = []
        with open(self.jpath) as json_data:
            data = json.load(json_data)
            for i, s in enumerate(data['shapes']):
                if s['shape_type'] == 'rectangle':
                    self.annotations.append(
                    AnnotationRectangle(s['points'][0][0], s['points'][0][1], x2 = s['points'][1][0], y2 = s['points'][1][1],
                        source="loaded from file", description = s['description'], label = s['label']
                                        )
                    )
                if s['label'] not in self.classes:
                    self.classes.append(s['label'])

    ### function for loading classes from a file
    def load_classes_file(self):
        self.classes = []
        with open(Path(self.src).parent / "classes.txt") as k:
            self.classes = k.read().splitlines()

            
### This page is the "wrapper" for the working image object, and it includes a lot of code to handle overlay, interface, and zooming

@ui.page('/img/{image_index}')
async def img_page(image_index: int):
        
    await ui.context.client.connected()

    # check whether the tab is still in an active session, if not reload.
    if 'overlay' not in app.storage.tab: app.storage.tab['overlay'] = False    
    if 'directory' not in app.storage.tab:
        ui.label('No active directory loaded, redirecting to start page')
        ui.navigate.to("/")
        print('Redirecting from annotations to main page')
        return

    focal_image = app.storage.tab['img_list'][image_index]
    pwd, pht = await ui.run_javascript('window.innerWidth'), await ui.run_javascript('window.innerHeight')
    imw, imh = Image.open(focal_image).size
    ratios = [imw/pwd, imh/pht]
    disp_w, disp_h = imw/max(ratios), imh/max(ratios)
    orig_x, orig_y = disp_w/2, disp_h/2
    overlay = True

    state = {'zoom': 1.0, 'pan_x': 0, 'pan_y': 0, 'dragging': False}
    
    with ui.card().tight().classes(f'w-full h-full overflow-hidden justify-center items-center bg-gray-100 relative select-none') as container:
        ui.add_css('''
        :root {
        --nicegui-default-padding: 0rem;
        }
        ''')
        # Wrap image in a div to manage transform origin
        with ui.element('div').classes(f'w-[{disp_w}px] h-[{disp_h}px] flex items-start justify-center') as wrapper:
            show_annotations=True
            wimg = WorkingImage(focal_image, show_annotations=show_annotations)
            wimg.initialize_image()
            ui.notify(f"Hotkeys are active, press H for help. Annotations are {'on' if show_annotations else 'off'}.")

            ### the formulas below have created a functional, responsive zoom
            ### they can 100% certainly be improved, it was very much a trial and error process
            def update_transform(x,y,magnify=True, pan=False):
                if not pan:
                    if x != orig_x:
                        xmod = -1 if ((state['pan_x'] * state['zoom'])/((x -orig_x)) < 1 and not magnify) else 1
                        state['pan_x'] = state['pan_x'] + xmod*((0.15*(orig_x - x))/(state['zoom']/0.5))
                    if y != orig_y:
                        ymod = -1 if ((state['pan_y'] * state['zoom'])/((y - orig_y)) < 1 and not magnify) else 1
                        state['pan_y'] = state['pan_y'] + ymod*((0.15*(orig_y - y))/(state['zoom']/0.5))
                x = f'{orig_x - state['pan_x']}px' #zoom to middle frame, with pan
                y = f'{orig_y - state['pan_y']}px' #zoom to middle frame, with pan
                wrapper.style(f'transform: translate({state["pan_x"]}px, {state["pan_y"]}px) scale({state["zoom"]}); transform-origin: {x} {y};')
                wrapper.update()
            
            # JavaScript wheel listener passed directly to container
            container.on('wheel', lambda e: handle_zoom(e))
            container.on('mousedown', lambda e: handle_drag_start(e))
            container.on('mousemove', lambda e: handle_drag(e))
            container.on('mouseup', lambda e: handle_drag_end(e))
    
            def handle_zoom(e):
                # e.args contains the raw JS wheel event dictionary
                delta = e.args.get('deltaY', 0)
                x, y = e.args.get('x'), e.args.get('y')
                if delta < 0:
                    state['zoom'] = min(state['zoom'] + 0.1, 5.0) # Cap max zoom at 5x
                    magnify=True
                else:
                    state['zoom'] = max(state['zoom'] - 0.1, 0.5) # Cap min zoom at 0.5x
                    magnify=False
                update_transform(x, y, magnify=magnify)
        
            def handle_drag_start(e):
                if e.args.get('button') == 1:
                    state['dragging'] = True
        
            def handle_drag(e):
                if state['dragging']:
                    x, y = e.args.get('x'), e.args.get('y')
                    # Adjust position adjustments relative to mouse movement
                    state['pan_x'] += e.args.get('movementX', 0)/state["zoom"]
                    state['pan_y'] += e.args.get('movementY', 0)/state["zoom"]
                    update_transform(x, y, pan=True)
        
            def handle_drag_end(e):
                if e.args.get('button') == 1:
                    state['dragging'] = False
        
            def modify_zoom(amount, magnify=True):
                if not magnify: amount = -1*amount
                state['zoom'] = max(0.5, min(state['zoom'] + amount, 5.0))
                update_transform(magnify=magnify)
            
            def reset_view():
                state['zoom'], state['pan_x'], state['pan_y'] = 1.0, 0, 0
                update_transform(x=orig_x, y=orig_y)
                
    ### The following _hotkeys function operates at a window level, not image level
    ### Help dialog describes all hotkeys, as the user experience won't distinguish page from object
    
    ### Visibility toggle adapted from https://www.reddit.com/r/nicegui/comments/1b1vf31/the_struggle_to_toggle_visibility/
    ## I can probably revise the hotkeys, help, and functions to be cleaner and more parsimonious.
    navigation_keys = {
        "ArrowLeft":f'/img/{image_index-1 if image_index-1 > 0 else 0}',
        "ArrowRight":f'/img/{image_index+1 if image_index+1 < len(app.storage.tab['img_list'])-1 else len(app.storage.tab['img_list'])-1}',
        "PageDown":f'/img/{image_index-1}',
        "PageUp":f'/img/{image_index+1}',
        "Home":f'/img/0/',
        "End":f'/img/{len(app.storage.tab['img_list'])-1}/',
        "Esc":'/gallery/'
    }

    last_keypress = None
    
    def _hotkeys(e: events.KeyEventArguments):
        
        if e.key in list(navigation_keys.keys()) and e.action.keydown and not e.action.repeat:
            nonlocal last_keypress
            if wimg.save_flag and (e.key != last_keypress):
                with ui.dialog(value=True) as dialog, ui.card():
                    ui.label('Hello world!')
                    ui.button('Close', on_click=dialog.close)
                dialog.open
                print("This should be dialog")
                
                last_keypress = e.key
                # spout warning that second tap will save and proceed; to clear annotations, press any other key to escape
            else:
                # save
                ui.navigate.to(navigation_keys[str(e.key)])
                    
        if e.key == 'r': reset_view()
        if e.key == 'o' and e.action.keydown:
            app.storage.tab['overlay'] = not app.storage.tab['overlay']
            label_overlay.clear()
            populate_classes()
            toggle_visibility(zoom_overlay)
            toggle_visibility(label_overlay)
            ui.notify(f"Overlay {"on" if app.storage.tab['overlay'] else "off"}")
        if e.key == 'j' and e.action.keydown:
            label_overlay.clear()
            populate_classes()
        if e.key == 'k' and e.action.keydown:
            label_overlay.clear()
        if e.key == 'h' and e.action.keydown:
            toggle_visibility(help_dialog)
            if help_dialog.visible: ui.notify("Good job, it's not always easy to ask for help")
        if e.key == 'p' and e.action.keydown:
            [print(vars(ann)) for ann in wimg.annotations]
        if e.key.number is not None and e.action.keydown and not e.action.repeat:
            if int(e.key.number)-1 < len(wimg.classes):
                wimg.active_class = wimg.classes[int(e.key.number)-1]
                label_overlay.clear()
                populate_classes()
            ui.notify(f'Active class now {wimg.active_class}')

    ### Toggle visibility (show/hide) of overlay/interface items
    def toggle_visibility(interface):
        interface.visible = not interface.visible

    ### Add a new class and programmatically generate a new color
    def new_class(event: events.GenericEventArguments):
        if event.sender.value not in wimg.classes:
            wimg.classes.append(event.sender.value)
            wimg.palette.append(number_to_color(len(wimg.palette)))
            wimg.save_flag = True
        if wimg.annotations == []:
            wimg.active_class = event.sender.value
        label_overlay.clear()
        populate_classes()

    ### Set class, only a function for the radio to call
    def set_class(e):
        wimg.active_class = e.value

    ### function that loads/refreshes/attends the class list overlay
    def populate_classes():
        with label_overlay:
            ui.label("Classes").classes('text-blue-500 font-bold text-lg')
            class_radio = ui.radio({x: x for x in wimg.classes}, value=wimg.active_class, on_change= lambda e: set_class(e))
            i = ui.input(label='New class', placeholder='start typing').props('clearable').on('keydown.enter',  new_class)

    ### Test box for diagnostics
    with ui.card().classes('fixed-center items-center').style('padding: 1rem').tight() as test_box:
        ui.label("Oh god how did this get here I am not good with computer").classes('text-blue-500 font-bold text-lg')
        test_box.visible = False

    ### Help dialog, always present, visibility toggled by H for Help
    with ui.card().classes('fixed-center items-center').style('padding: 1rem').tight() as help_dialog:
        ui.label("Help").classes('text-blue-500 font-bold text-lg')
        ui.space()
        ui.label('A: show/hide annotations')
        ui.label('C: clear new annotations')
        ui.label('E: enter/exit editing mode')
        ui.label('S: save/export annotations')
        ui.label('O: show/hide overlay')
        ui.label('scroll to zoom in or out')
        ui.label('scroll-click to pan around')
        ui.label('R: reset view')
        ui.label('D: delete last box')
        ui.label('C: clear all unsaved boxes')
        ui.label('#: pick class from list for labeling')
        ui.space()
        ok_button = ui.button('OK', on_click=lambda: toggle_visibility(help_dialog))
        help_dialog.visible = False

    ### Zoom buttons, always present, visibility toggled by O for Overlay
    with ui.row().classes('absolute bottom-2 right-2 bg-white p-1 rounded shadow') as zoom_overlay:
        zoom_in_b = ui.button(icon='zoom_in', on_click=lambda: modify_zoom(0.2, magnify=True))
        zoom_out_b = ui.button(icon='zoom_out', on_click=lambda: modify_zoom(0.2, magnify=False))
        zoom_reset_b = ui.button(icon='refresh', on_click=lambda: reset_view())
        zoom_overlay.visible = app.storage.tab['overlay']

    ### Create the parent for the class overlay, always present, toggled by O for Overlay
    label_overlay = ui.card().classes('border p-4 absolute right-2').style('padding: 1rem').tight()
    populate_classes()
    label_overlay.visible=app.storage.tab['overlay']
    
    ui.keyboard(on_key=_hotkeys)

ui.run()