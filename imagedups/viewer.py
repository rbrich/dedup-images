import os.path
import tkinter
import tkinter.messagebox
from subprocess import Popen, DEVNULL
from functools import partial


class ViewHelper:

    def __init__(self, title, file_list, viewer):
        self._viewer = viewer
        self._file_list = file_list
        self._p = None
        self._want_next = False

        root = self.root = tkinter.Tk()
        root.title(title)
        root.protocol("WM_DELETE_WINDOW", self._quit)
        root.after(200, self._timer)

        btn_next = self.btn_next = tkinter.Button(root)
        btn_next["text"] = "Next",
        btn_next["command"] = self._next
        btn_next.pack({"side": "left"})

        btn_quit = self.btn_quit = tkinter.Button(root)
        btn_quit["text"] = "Quit"
        btn_quit["command"] = self._quit
        btn_quit.pack({"side": "left"})

        self.buttons = []
        prefix = os.path.commonprefix(file_list)
        prefix_len = len(prefix)
        # When prefix ends with slash, keep it
        if prefix and prefix[-1] == '/':
            prefix_len -= 1
        for fname in file_list:
            btn = tkinter.Button(root)
            btn["text"] = "Delete ..." + fname[prefix_len:]
            btn["command"] = partial(self._delete, fname, btn)
            btn.pack({"side": "left"})
            self.buttons.append(btn)

    def main(self):
        self._p = Popen([self._viewer] + self._file_list,
                        stdout=DEVNULL, stderr=DEVNULL)
        self.root.mainloop()
        return self._want_next

    def _next(self):
        self._want_next = True
        self._quit()

    def _quit(self):
        self._p.terminate()
        self._p.wait()
        self.root.destroy()

    def _delete(self, filename, btn):
        if tkinter.messagebox.askyesno("Confirm file deletion",
                                       "Delete %s?" % filename,
                                       icon=tkinter.messagebox.WARNING):
            os.unlink(filename)
            btn['state'] = 'disabled'

    def _timer(self):
        status = self._p.poll()
        if status is not None:
            self._want_next = (status == 0)
            self._p.wait()
            self.root.destroy()
        else:
            self.root.after(200, self._timer)


if __name__ == '__main__':
    res = ViewHelper("test 1", [], 'gthumb').main()
    print("next:", res)
    if res:
        ViewHelper("test 2", [], 'gthumb').main()
