# lazytokens.py
#
# handles the idea of tokens which may be evaluated at a later time.

import streams

class Token(object) :
    line = 0
    streamname = "*unknown*"
    def __init__(self, stream=None) :
        if stream is not None :
            self.streamerr = stream.failure() # save it for later
        else :
            self.streamerr = None
    def fail(self, message) :
        if self.streamerr == None :
            raise Exception(message)
        else :
            raise self.streamerr.with_message(message)
    def eval(self, env) :
        """Should return itself in simplified form.  The env variable
        is a dictionary which can be used by the tokens for
        evaluation."""
        raise NotImplementedError("Token needs eval")
    def __add__(self, token2) :
        if type(token2) == ListToken :
            return ListToken([self] + token2.tokens)
        else :
            return ListToken([self, token2])

class SelfEvaluatingToken(Token) :
    def eval(self, env) :
        return self
    def __eq__(self, other) :
        return type(self) == type(other)

class StringToken(SelfEvaluatingToken) :
    def __init__(self, s) :
        SelfEvaluatingToken.__init__(self, None)
        self.s = s
    def __add__(self, token2) :
        if type(token2) == StringToken :
            return StringToken(self.s + token2.s)
        elif type(token2) == ListToken and len(token2.tokens) > 0 and type(token2.tokens[0]) == StringToken :
            return (self + token2.tokens[0]) + ListToken(token2.tokens[1:])
        else :
            return Token.__add__(self, token2)
    def __repr__(self) :
        return "<StringToken name="+repr(self.s)+">"
    def __eq__(self, other) :
        return (type(other) == StringToken) and (self.s == other.s)

class ParagraphToken(SelfEvaluatingToken) :
    pass

class InhibitParagraphToken(SelfEvaluatingToken) :
    pass

class EOFToken(SelfEvaluatingToken) :
    pass

class ItemToken(SelfEvaluatingToken) :
    def __init__(self, stream, textlabel) :
        SelfEvaluatingToken.__init__(self, stream)
        self.textlabel = textlabel

class ColumnBreakToken(SelfEvaluatingToken) :
    pass

class LineBreakToken(SelfEvaluatingToken) :
    pass

class HorizontalLineToken(SelfEvaluatingToken) :
    pass

class EndEnvToken(SelfEvaluatingToken) :
    def __init__(self, name) :
        self.name = name
    def __eq__(self, other) :
        if type(other) == EndEnvToken :
            return self.name == other.name
        else :
            return False
    def __repr__(self) :
        return "<EndEnvToken name="+repr(self.name)+">"

class VariableToken(Token) :
    def __init__(self, name) :
        self.n = name
    def eval(self, env) :
        if env.has_key(self.n) :
            return env[self.n]
        else :
            raise AttributeError("Line "+str(self.line)+" in "+repr(self.streamname)+". No binding for "+repr(self.n)+".")
    def __repr__(self) :
        return "<VariableToken name="+repr(self.n)+">"

class LambdaToken(Token) :
    def __init__(self, f) :
        """f must be a lambda of one variable: the environment."""
        Token.__init__(self, None)
        self.f = f
    def eval(self, env) :
        return self.f(env).eval(env)

class ListToken(Token) :
    def __init__(self, tokens) :
        Token.__init__(self, None)
        self.tokens = list(tokens)
    def eval(self, env) :
        evaled = reduce(lambda lst, e : lst + e, [e.eval(env) for e in self.tokens])
        if type(evaled) == ListToken and len(evaled.tokens) == 1 :
            return evaled.tokens[0]
        else :
            return evaled
    def __add__(self, token2) :
        if len(self.tokens) == 0 :
            return token2
        elif type(token2) == ListToken :
            return ListToken(self.tokens + token2.tokens)
        elif type(token2) == StringToken and len(self.tokens) > 0 and type(self.tokens[-1]) == StringToken :
            return ListToken(self.tokens[:-1]) + (self.tokens[-1] + token2)
        else :
            return ListToken(self.tokens + [token2])
    def __repr__(self) :
        return "<ListToken tokens="+repr(self.tokens)+">"

class ArgumentToken(Token) :
    def __init__(self, token) :
        self.token = token
    def eval(self, env) :
        return ArgumentToken(self.token.eval(env))
    def __repr__(self) :
        return "<ArgumentToken token="+repr(self.token)+">"
