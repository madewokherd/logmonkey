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
    
    logged_session.write("## Command: %s\n" % ' '.join(repr(x) for x in argv))

    dump_env(os.environ, logged_session)
    
    logged_session.write("## Starting process...\n")

    logged_process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    logged_session.set_process(logged_process)
    
    logged_session.wait()

cli_main(sys.argv[1:])

