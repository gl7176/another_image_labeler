import math, json, os, csv
from nicegui import ui, events, app
from pathlib import Path
import subpages.annotation_page

class Lightbox:
    """A thumbnail gallery where each image can be clicked to enlarge.
    Inspired by https://lokeshdhakar.com/projects/lightbox2/.
    """

    def __init__(self, directory, img_list) -> None:
        self.image_list = sorted(img_list)
        self.directory = directory
        self.loadcount = 0
        with ui.dialog().props('maximized').classes('bg-black') as self.dialog:
            ui.keyboard(self._handle_key)
            self.large_image = ui.image().props('no-spinner fit=scale-down')

    def get_ann_stat(self, orig_url: str):
        jpath = Path(self.directory / f'{str(Path(orig_url).stem)}.json')
        json_list = list(self.directory.glob(f"**/*.json"))
        return jpath in json_list
        # eventually globalize this function?
    
    def add_image(self, orig_url: str) -> ui.image:
        annotation_status = self.get_ann_stat(orig_url)
        """Place a thumbnail image in the UI and make it clickable to enlarge."""
        if annotation_status: button_color, annotation_desc = 'orange', 'Annotated'
        else: button_color, annotation_desc = 'blue', "Not annotated"
        with ui.button(on_click=lambda: self._open(orig_url)).props('flat dense square'):
            ui.button(annotation_desc).classes('absolute-full text-subtitle2 flex flex-center').props(f'color={button_color}')
            ui.tooltip(str(Path(orig_url).name)).classes('bg-green')
            return ui.image(orig_url)

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        if not event_args.action.keydown:
            return
        if event_args.key.escape:
            self.dialog.close()
        image_index = self.image_list.index(self.large_image.source)
        if (event_args.key == "PageDown" or event_args.key.arrow_left) and image_index > 0:
            self._open(self.image_list[image_index - 1])
        if (event_args.key == "PageUp" or event_args.key.arrow_right) and image_index < len(self.image_list) - 1:
            self._open(self.image_list[image_index + 1])
        if event_args.key.arrow_up:
            ui.notify(self.large_image.source)
        if event_args.key == '\\' or event_args.key.enter:
            new_url = '/img_page?{image_index}'
            ui.navigate.to(f'/img/{image_index}')
        if event_args.key == "a" and event_args.action.keydown:
            ui.notify('Still browsing images in preview mode. Press "Enter" to begin annotating.')

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        self.dialog.open()
        ui.notify('Browsing images in preview mode. Press "Enter" to begin annotating.')

@ui.page('/gallery/')
async def gallery():
    await ui.context.client.connected()

    if 'directory' not in app.storage.tab:
        ui.label('No active directory loaded, redirecting to start page')
        ui.navigate.to('/')
        print(f'Redirecting from gallery to main page')
        return
    
    with ui.header(elevated=False).style('background-color: #3874c8').classes('py-1 min-h-0 items-center w-full justify-between').props('reveal reveal-offset=0') as parent: 
        ui.label(f'Loading directory: {str(app.storage.tab['directory'])}').classes('text-xs')
        ui.button(on_click=lambda: right_drawer.toggle(), icon='menu').props('flat color=white size=xs')          
    with ui.right_drawer(fixed=False).style('background-color: #ebf1fa').props('bordered') as right_drawer:
        ui.label('RIGHT DRAWER')
    right_drawer.toggle()

    
    img_exts = ["jpg", "bmp", "png", "tif"]

    prescreen_file = app.storage.tab['directory'] / f'{app.storage.tab['directory'].stem}_prescreened.csv'
    if os.path.exists(prescreen_file):
        with open(prescreen_file, newline='') as f:
            data = list(csv.reader(f))
        app.storage.tab['img_list'] = [r[2] for r in data[1:] if r[-4]=='True']
        print('Prescreen file loaded')
    else: 
        print(f'No prescreen file identified matching {prescreen_file}')
        app.storage.tab['img_list'] = [str(val) for sublist in [
            list(app.storage.tab['directory'].glob(f"**/*.{x}")) for x in img_exts
        ] for val in sublist]
    
    
    lightbox = Lightbox(app.storage.tab['directory'], app.storage.tab['img_list'])
    
    def calc_load_quantity(win_w, win_h, thumb_w, thumb_h, buffer=20):
        cols = (win_w - buffer)/(thumb_w + buffer)    # col width = thwd*x   +   buffer*(x+1)
        rows = (win_h - buffer)/(thumb_h + buffer)    # row height = thht*x   +   buffer*(x+1)
        return (int(cols) * int(rows+1))


    ### The scroll function was adapted from https://github.com/zauberzeug/nicegui/blob/main/examples/infinite_scroll/main.py
    async def check_for_scroll():
        try:
            pwd, pht = await ui.run_javascript('window.innerWidth'), await ui.run_javascript('window.innerHeight')
            thumb_w, thumb_h = 300, 200
            loadquant = calc_load_quantity(pwd, pht, thumb_w, thumb_h)
            pg_y_off, doc_bod_off = await ui.run_javascript('window.pageYOffset'), await ui.run_javascript('document.body.offsetHeight')
            if (pg_y_off % pht) + 1 > doc_bod_off % pht:
                with ui.row().classes('w-full'):
                    t = math.ceil((doc_bod_off/pht)-1)
                    for image_path in app.storage.tab['img_list'][loadquant*t:loadquant*(t+1)]:
                        lightbox.add_image(
                            orig_url=f'{image_path}',
                        ).classes(f'w-[{thumb_w}px] h-[{thumb_h}px]')
                        lightbox.loadcount += 1
                        #print(Path(image_path).stem)
        except TimeoutError:
            pass  # the client might have disconnected
    await ui.context.client.connected()
    t=0
    ui.timer(0.1, check_for_scroll)

ui.run(reload=False)