# Another image labeler!

<img src="https://raw.githubusercontent.com/gl7176/another_image_labeler/refs/heads/main/AIL-screenshot.png" alt="AIL in action!!" width="600">

You might be asking yourself "why might I need another image labeler?" It's a good question, and maybe you don't. There are lots of good image labelers out there with better code, cleaner interfaces, and more versatility than this one. Some good starting places are:

https://labelstud.io/

https://github.com/cvhub520/x-anylabeling

https://github.com/wkentaro/labelme

and a personal favorite of mine:

https://www.robots.ox.ac.uk/~vgg/software/via/

<img src="https://cdn-v2.meme.com/memes/y-tho/y-tho-iconic-meme.webp" alt="but y tho" width="300">

So why did I make another image labeler? Because I have tried all of these interfaces and labeled a lot of images in my time, and I have strong opinions and complaints about almost every label maker I've used.

Some of them are require too much time per-label: they require a manually assigned label for each annotation, they require clicking through multiple dialogs to complete a label, or they simply don't have hotkeys.
Some of them make it difficult to import, export, and share annotations across multiple users, or they are optimized for a database or cloud-based system.
Some of them don't allow you to zoom and pan as you're annotating the image.
Many of them don't interface seemlessly with customizeable AI models for both training and predicting.
All of them are coded by people who are better coders than me, and are therefore not easy for an amateur like me to customize.

So I am building an annotation interface that aims for (1) simplicity - few dependencies, minimal "interface", limited code complexity, (2) efficiency - intuitive hotkeys, sensible assumptions to reduce unneccessary actions, only essential clicks-per-label, (3) maximum compatibility in the model training inputs and outputs, such that the same annotation interface can be used to create new labels or correct model predictions.
The hope is to build a simple interface that blends annotation and model training/deployment for a human-in-the-loop image review cycle.

After looking around for a bit, I settled on ["NiceGUI"](https://nicegui.io/) as my GUI toolkit, and the functionality I'm building is heavily based on what I liked from [VIA](https://www.robots.ox.ac.uk/~vgg/software/via/).
The program reads in a target directory (provided by user), allows users to preview images, then load a single image at a time (with easy navigation between images within the target directory) to draw annotations.
Annotations are then exported to a JSON file for each image annotated in a standard format that can be easily collated and reformatted for various ML frameworks (coco, yolo, etc.).


# The goal
This program is being developed for a project that is facing a large and growing volume of messy (highly variable) image data. The project hopes that computer vision will help alleviate the burdensome effort of reviewing all images, and I am not sure how much training data a model would require to become proficient with our messy data, or where the return-on-investment might occur.

If we can achieve a [human-in-the-loop](https://www.ibm.com/think/topics/human-in-the-loop) design, we can begin to manually review and annotate the data while periodically training and evaluating models as we go (even just qualitatively at-a-glance). If the models ever start to become useful, we can begin to incorporate their predictions, which will hopefully accelerate the task of reviewing images.

By using our own customized labeler, we can also track the relative effort (as time) of manual annotations, the improving (or not) state of our models, and the potential effort saved if the fully manual review effort becomes partially automated.

# Current status
At this stage I have achieved a simple bounding-box labeler with the core functions that I would want in such a program (zoom, pan, create new boxes, select and delete boxes, add labels, set the label of new boxes). And many hotkeys. I may add additional functionality in the future (e.g. modify existing boxes, modify existing labels, copy-paste existing boxes).
However, for now I am pivoting to the "model training" component of the project, which will inform how I can export training data and import predictions from said models into the annotation interface. I am hoping that the core "loop" (annotation, periodic training, and prediction) can achieve functional deployment and use across our team-members before we get bogged down in luxury features.

# Installation
Clone or download the files and install the dependencies in _requirements.txt_ (I recommend using a virtual environment, but you do you).

# Running the program
Open your terminal of choice, activate the appropriate python environment if using virtual environments, navigate to the directory where _AIL.py_ lives, and launch with prompt _>python AIL.py_.

# Questions a reasonable person might ask
Q: ***Can I request new features?***

A: Yes, but I can't promise a timeline on their delivery. Feel free to email me at [gregorydlarsen@gmail.com](mailto:gregorydlarsen@gmail.com)



Q: ***Why doesn't your program do this thing I want?***

A: Probably becuase I haven't had the time, need, or ability to code it. 



Q: ***Can I steal and adapt your code for my own project?***

A: Can? Yes. Should? Probably not.



Q: ***This code is bad and you should feel bad.***

A: I am aware, and that is actually more of a statement than a question.
