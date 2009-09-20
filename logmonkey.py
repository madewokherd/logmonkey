#!/usr/bin/env python
# Copyright (c) 2009 Vincent Povirk
# 
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

import os
import sys
import subprocess
import threading

class ReadPipeThread(threading.Thread):
    def __init__(self, session, pipe):
        threading.Thread.__init__(self)
        self.session = session
        self.pipe = pipe
    
    def run(self):
        buf = ''
        #We have to do low-level I/O with the pipe because file-like objects do
        # buffering which can delay the read.
        fileno = self.pipe.fileno()
        try:
            while True:
                readdata = os.read(fileno, 4096)
                if not readdata:
                    break
                buf = '%s%s' % (buf, readdata)
                if '\n' in buf:
                    info, buf = buf.rsplit('\n', 1)
                    self.session.write(info, '\n')
        except IOError: # broken pipe
            pass
        self.session.write(buf)

class ProcessWaitThread(threading.Thread):
    def __init__(self, session):
        threading.Thread.__init__(self)
        self.session = session
    
    def run(self):
        retval = self.session.process.wait()
        self.session.write('## Process returned %i\n' % retval)

class LoggedSession(object):
    def __init__(self):
        self.lock = threading.Lock()
    
    def spin(self):
        "update some progress bar / spinner"
        pass
    
    def write(self, *args):
        "write bytes to the output file, making sure they are kept intact"
        # we lock here so that we know "info" will not be broken up
        self.lock.acquire()
        try:
            for arg in args:
                self.outfile.write(arg)
        finally:
            self.lock.release()
        
        self.spin()

    def set_process(self, process):
        "log and wait for a subprocess.Popen object"
        self.process = process
        threads = []
        if process.stdout is not None:
            threads.append(ReadPipeThread(self, process.stdout))
        if process.stderr is not None:
            threads.append(ReadPipeThread(self, process.stderr))
        threads.append(ProcessWaitThread(self))
        self.threads = threads
        for thread in threads:
            thread.start()
    
    def wait(self):
        for thread in self.threads:
            thread.join()

def dump_env(env, session):
    output = ['## Environment variables:\n']
    for key, value in env.iteritems():
        output.append('##     %s = %s\n' % (repr(key), repr(value)))
    session.write(''.join(output))

def cli_main(argv):
    logged_session = LoggedSession()
    
    logged_session.outfile = sys.stdout
    
    logged_session.write("## Command: %s\n" % ' '.join(repr(x) for x in argv[1:]))

    dump_env(os.environ, logged_session)
    
    logged_session.write("## Starting process...\n")

    logged_process = subprocess.Popen(argv[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    logged_session.set_process(logged_process)
    
    logged_session.wait()



# BEGIN PYGTK-SPECIFIC CODE

import threading
import time

import gobject

gobject.threads_init()

import gtk

gtk.gdk.threads_init()


class SpinnyLoggedSession(gtk.Dialog, LoggedSession):
    def __init__(self, *args, **kwargs):
        gtk.Window.__init__(self, *args, **kwargs)
        LoggedSession.__init__(self)

        self.set_property('focus-on-map', False)

        self.label = gtk.Label()
        self.label.show()
        self.vbox.add(self.label)

        self.progress = gtk.ProgressBar()
        self.progress.show()
        self.vbox.add(self.progress)

        self.add_button('Stop Logging', gtk.RESPONSE_CLOSE)

        self.last_spin_time = time.time()

    def set_label(self, str):
        self.label.set_label(str)

    def spin(self):
        if time.time() - self.last_spin_time >= 0.2:
            gobject.idle_add(self.progress.pulse)
            self.last_spin_time = time.time()

    def _thread_proc(self, args):
        self.outfile = sys.stdout
        
        self.write("## Command: %s\n" % ' '.join(repr(x) for x in args))

        dump_env(os.environ, self)
        
        self.write("## Starting process...\n")

        self.set_label("Starting process")

        logged_process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.set_process(logged_process)

        self.set_label("Waiting for process to close")
        
        self.wait()

        self.response(gtk.RESPONSE_CLOSE)

    def run(self, args):
        self.thread = threading.Thread(target=self._thread_proc, args=(args,))
        self.thread.start()

        gtk.Dialog.run(self)

def pygtk_main(argv):
    logged_session = SpinnyLoggedSession()

    logged_session.run(argv[1:])



main = pygtk_main

if __name__ == '__main__':
    sys.exit(main(sys.argv))

