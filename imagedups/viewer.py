import tkinter
from subprocess import Popen, DEVNULL


class ViewHelper:

    def __init__(self, viewer, file_list):
        self._viewer = viewer
        self._file_list = file_list
        self._p = None
        self._want_next = False

        root = self.root = tkinter.Tk()
        root.title("imagedups helper")
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

    def _timer(self):
        status = self._p.poll()
        if status is not None:
            self._want_next = (status == 0)
            self._p.wait()
            self.root.destroy()
        else:
            self.root.after(200, self._timer)


if __name__ == '__main__':
    res = ViewHelper('gthumb', []).main()
    print("next:", res)
    if res:
        ViewHelper('gthumb', []).main()
