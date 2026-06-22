import os, pathlib, glob, time, math, json, copy, datetime
from PIL import Image
from pathlib import Path
from nicegui import ui, events, app
import subpages.gallery

base_directory = None
#base_directory = r"C:\Users\gdlarsen\OneDrive - State of Alaska\Documents\Annotating data\KBay\Peterson-Bay_Moss-Island\2025_10\CAM02-NC\PHOTO_100RECNX"
if base_directory is not None:
    base_directory = Path(base_directory)
    if not os.path.isdir(base_directory):
        base_directory = None

@ui.page('/')
async def page():

    await ui.context.client.connected()
    
    async def set_directory():
        base_directory=Path(inputbox.value)
        if os.path.isdir(base_directory):
            parent.clear()
            ui.label(f'Base directory received: {str(base_directory)}').classes('text-xs justify-between')
            app.storage.tab['directory'] = base_directory
            ui.navigate.to('/gallery/')
        else: ui.notify("Entered path is not an accessible directory")
        
    with ui.header(elevated=False).style('background-color: #3874c8').classes('py-1 min-h-0 items-center w-full justify-between').props('reveal reveal-offset=0') as parent: 
        if base_directory:
            ui.label(f'Base directory hard-coded: {str(base_directory)}').classes('text-xs')
            app.storage.tab['directory'] = base_directory
            ui.navigate.to('/gallery/')
        else:
            inputbox = ui.input(label='Input path for a directory', placeholder='start typing here').on('keydown.enter', set_directory).props('clearable').style('width: 500px')

# might code for window resize sometime

ui.run(reload=False)