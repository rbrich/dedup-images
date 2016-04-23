import os.path
import tkinter
import tkinter.messagebox
from subprocess import Popen, DEVNULL
from functools import partial
from collections import namedtuple
from PIL import Image, ImageTk


class ViewHelper:

    def __init__(self, title, file_list, viewer):
        self._viewer = viewer
        self._file_list = sorted(file_list)
        self._processes = []
        self._want_next = False

        root = self.root = tkinter.Tk()
        root.title(title)
        root.protocol("WM_DELETE_WINDOW", self._quit)
        root.bind('n', lambda _ev: self._next())
        root.bind('q', lambda _ev: self._quit())

        frm_group = self.frm_group = tkinter.Frame(root)
        frm_group.pack(side=tkinter.BOTTOM, padx=8, pady=8)

        btn_next = self.btn_next = tkinter.Button(frm_group, text="Next")
        btn_next["command"] = self._next
        btn_next.pack(side=tkinter.LEFT)

        btn_quit = self.btn_quit = tkinter.Button(frm_group, text="Quit")
        btn_quit["command"] = self._quit
        btn_quit.pack(side=tkinter.LEFT)

        # Common file name prefix in the group
        prefix = os.path.commonprefix(file_list)
        prefix_len = len(prefix)
        # When prefix ends with slash, keep it
        if prefix and prefix[-1] == '/':
            prefix_len -= 1

        lbl_path = self.lbl_path = tkinter.Label(root, text=prefix + "...")
        lbl_path.pack(side=tkinter.TOP, padx=8, pady=8)

        image_info = {}
        ImageInfo = namedtuple('ImageInfo', ['image', 'filename', 'filesize',
                                             'pixelsize', 'imageformat'])
        for fname in file_list:
            # Probe image, make thumbnail
            image = Image.open(fname)
            filename = "..." + fname[prefix_len:] if prefix_len > 0 else fname
            filesize = "{:,} B".format(os.path.getsize(fname))
            pixelsize = "%s x %s" % image.size
            imageformat = "%s / %s" % (image.format, image.mode)
            image.thumbnail((128, 128))
            image_info[fname] = ImageInfo(image, filename,
                                          filesize, pixelsize, imageformat)

        self.image_frames = []
        for fname in file_list:
            info = image_info[fname]
            d_fsize = any(i.filesize != info.filesize
                          for i in image_info.values())
            d_psize = any(i.pixelsize != info.pixelsize
                          for i in image_info.values())

            # Frame for image and info
            frm = tkinter.Frame(root, bd=1, relief=tkinter.SUNKEN, height=2)
            frm.pack(fill=tkinter.X)
            frm.grid_rowconfigure(3, weight=1)
            frm.grid_columnconfigure(0, pad=8)
            frm.grid_columnconfigure(2, pad=8)

            # Image button
            photo_image = frm.ref_photo_image = ImageTk.PhotoImage(info.image)
            imgbtn = frm.ref_imgbtn = tkinter.Button(frm, image=photo_image)
            imgbtn["command"] = partial(self._open, fname)
            imgbtn.grid(row=0, rowspan=5, column=0, pady=8)

            # Info labels
            def add_info(row, name, value, differs=False):
                color = "red2" if differs else None
                pad = (8, 0) if row == 0 else 0
                label_name = tkinter.Label(frm, text=name)
                label_name.grid(row=row, column=1, sticky=tkinter.NW, pady=pad)
                label_value = tkinter.Label(frm, text=value, fg=color)
                label_value.grid(row=row, column=2, sticky=tkinter.NW, pady=pad)
                return label_name, label_value
            frm.ref_fname = add_info(0, "File name:", info.filename)
            frm.ref_fsize = add_info(1, "File size:", info.filesize, d_fsize)
            frm.ref_pxsize = add_info(2, "Pixel size:", info.pixelsize, d_psize)
            frm.ref_format = add_info(3, "Format:", info.imageformat)

            # Delete button
            btn = frm.ref_btn = tkinter.Button(frm)
            btn["text"] = "Delete"
            btn["command"] = partial(self._delete, fname, frm)
            btn.grid(row=4, column=1, columnspan=2, sticky=tkinter.SW, pady=8)

            # Keep references
            self.image_frames.append(frm)

    def main(self):
        self.root.mainloop()
        return self._want_next

    def _next(self):
        self._want_next = True
        self._quit()

    def _quit(self):
        for p in self._processes:
            p.terminate()
            p.wait()
        self.root.destroy()

    def _open(self, filename):
        p = Popen([self._viewer, filename], stdout=DEVNULL, stderr=DEVNULL)
        self._processes.append(p)

    def _delete(self, filename, frm):
        if tkinter.messagebox.askyesno("Confirm file deletion",
                                       "Delete %s?" % filename,
                                       icon=tkinter.messagebox.WARNING):
            os.unlink(filename)
            frm.ref_btn['state'] = 'disabled'
            frm.ref_imgbtn['state'] = 'disabled'


if __name__ == '__main__':
    res = ViewHelper("test 1", [], 'gthumb').main()
    print("next:", res)
    if res:
        ViewHelper("test 2", [], 'gthumb').main()
