# environments.py

class CharacterEnvironment(object) :
    def __init__(self, bindings, parent) :
        self.bindings = bindings
        self.parent = parent
    def __getitem__(self, key) :
        if self.bindings.has_key(key) :
            return self.bindings[key]
        else :
            return self.parent[key]
    def __setitem__(self, key, value) :
        self.bindings[key] = value
    def get_bindings(self) :
        bindings = self.parent.get_bindings()
        for key, val in self.bindings.iteritems() :
            bindings[key] = val
        return bindings
    def extend(self, extendWith=None) :
        if extendWith==None :
            extendWith = {}
        return CharacterEnvironment(extendWith, self)
    def __repr__(self) :
        return "<CharacterEnvironment bindings="+repr(self.bindings)+" parent="+repr(self.parent)+">"

class DefaultCharacterEnvironment(CharacterEnvironment) :
    def __init__(self, handler) :
        self.handler = handler
    def __getitem__(self, key) :
        return self.handler
    def __setitem__(self, key, value) :
        raise Exception("Default character environment can not be set.")
    def get_bindings(self) :
        return dict()
    def extend(self, extendWith=None) :
        if extendWith==None :
            extendWith = {}
        return CharacterEnvironment(extendWith, self)
    def __repr__(self) :
        return "<DefaultCharacterEnvironment handler="+repr(self.handler)+">"

def add_char_handler(char_env, char) :
    def add_handler(f) :
        char_env[char] = f
        return f
    return add_handler

def add_token_handler(token_env, name) :
    def add_handler(f) :
        token_env[name] = f
        return f
    return add_handler

class TokenEnvironment(object) :
    def __init__(self, bindings, parent=None) :
        self.bindings = bindings
        self.parent = parent
    def __getitem__(self, key) :
        if self.bindings.has_key(key) :
            return self.bindings[key]
        elif self.parent is not None :
            return self.parent[key]
        else :
            print self
            raise KeyError(key)
    def has_key(self, key) :
        if self.bindings.has_key(key) :
            return True
        elif self.parent is not None :
            return self.parent.has_key(key)
        else :
            return False
    def __setitem__(self, key, value) :
        self.bindings[key] = value
    def get(self, k, d=None) :
        try :
            return self[k]
        except KeyError :
            return d
    def extend(self, extendWith=None) :
        if extendWith==None :
            extendWith = {}
        return TokenEnvironment(extendWith, self)
    def __repr__(self) :
        return "<TokenEnvironment bindings="+repr(self.bindings)+" parent="+repr(self.parent)+">"
