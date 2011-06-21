# streams.py
#
# supports peeking in a file

class ParseException(Exception) :
    def __init__(self, msg, line=None, name="*unspecified*") :
        self.msg = msg
        self.line = line
        self.name = name
    def with_message(self, msg) :
        return ParseException(msg, self.line, self.name)
    def __str__(self) :
        if self.line :
            return "Line "+str(self.line)+" in "+repr(self.name)+". "+str(self.msg)
        else :
            return str(msg)

class Stream(object) :
    def __init__(self, name) :
        self.name = name
        self.row = 1
    def read(self) :
        raise NotImplementedError("Stream needs read.")
    def peek(self) :
        raise NotImplementedError("Stream needs peek.")
    def failure(self, msg="Unknown error.") : # returns an exception object which can be raised
        return ParseException(msg, self.row, self.name)
    
    def read_while(self, chars) :
        s = ""
        c = self.peek()
        while c != "" and c[0] in chars :
            s += self.read()
            c = self.peek()
        return s
    def read_while_not(self, chars) :
        s = ""
        c = self.peek()
        while c != "" and c[0] not in chars :
            s += self.read()
            c = self.peek()
        return s
    def read_while_p(self, predicate) :
        s = ""
        c = self.peek()
        while c != "" and predicate(c[0]) :
            s += self.read()
            c = self.peek()
        return s

class StringStream(Stream) :
    def __init__(self, str) :
        Stream.__init__(self, "*string*")
        self.str = str
        self.i = 0
    def read(self) :
        if self.i == len(self.str) :
            return ''
        else :
            self.i += 1
            if self.str[self.i-1] == '\n' :
                self.row += 1
            return self.str[self.i-1]
    def peek(self) :
        if self.i == len(self.str) :
            return ''
        else :
            return self.str[self.i]

class PeekStream(Stream) :
    def __init__(self, file) :
        Stream.__init__(self, repr(file))
        self.file = file
        self.peeked = False
        self.peek_char = ''
    def read(self) :
        if self.peeked :
            self.peeked = False
            return self.peek_char
        else :
            ret = self.file.read(1) # is '' when EOF
            if ret == '\n' :
                self.row += 1
            return ret
    def peek(self) :
        if self.peeked :
            return self.peek_char
        else :
            self.peek_char = self.read()
            self.peeked = True
            return self.peek_char

# this is like the open(...) function, but only for reading
def fileStream(filename) :
    stream = PeekStream(open(filename, "r"))
    stream.name = filename
    return stream
