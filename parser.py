# parser.py
#
# the basic parser which handles tokens, etc.

import streams
import environments
from environments import (CharacterEnvironment, DefaultCharacterEnvironment, TokenEnvironment, add_char_handler, add_token_handler)
import lazytokens
from lazytokens import (StringToken, LambdaToken, ListToken, VariableToken, ArgumentToken, EndEnvToken)
import os.path

tokenNameChars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def parse_one(stream, char_env, escape_env, begin_stack) :
    return char_env[stream.peek()](stream, char_env, escape_env, begin_stack)

# for global-level parsing, maybe (and testing)
def parse_all(stream, char_env, escape_env, begin_stack, execute = False) :
    out = parse_one(stream, char_env, escape_env, begin_stack)
    if execute :
        out = out.eval({})
    while stream.peek() != "" :
        a = parse_one(stream, char_env, escape_env, begin_stack)
        if execute :
            out += a.eval({})
        else : out += a
    return out

def global_parse(stream) :
    return parse_all(stream, global_char_env, global_tokens, [], execute = True)

def default_handler(stream, char_env, escape_env, begin_stack) :
    bound = char_env.get_bindings()
    return StringToken(stream.read_while_not(bound))

global_char_env = CharacterEnvironment({}, DefaultCharacterEnvironment(default_handler))
global_tokens = TokenEnvironment({})

def global_char_handler(char) :
    return add_char_handler(global_char_env, char)

def global_token(name) :
    return add_token_handler(global_tokens, name)

# handles EOF
@global_char_handler('')
def eof_handler(stream, char_env, escape_env, begin_stack) :
    return lazytokens.EOFToken()

# handles comments
@global_char_handler('%')
def comment_handler(stream, char_env, escape_env, begin_stack) :
    stream.read_while_not("\n")
    return StringToken("")

# handles \escape tokens
@global_char_handler('\\')
def token_handler(stream, char_env, escape_env, begin_stack) :
    stream.read()
    name = stream.read_while(tokenNameChars)
    if name == "" :
        c = stream.read()
        if c == "" :
            raise stream.failure("End of file reached for token.  Expecting name.")
        else :
            if escape_env.has_key(c) :
                handler = escape_env[c]
            else :
                raise stream.failure("No such single character escape token "+repr(c)+".")
    else :
        if escape_env.has_key(name) :
            handler = escape_env[name]
        else :
            raise stream.failure("No such escape token "+repr(name)+".")
        stream.read_while(" ") # gobble spaces (only if non-symbol escape token)
    return handler(stream, char_env, escape_env, begin_stack)

# for supporting \var{name}
@global_token("var")
def var_token(stream, char_env, escape_env, begin_stack) :
    possible_error = stream.failure("Variable name must be string.")
    arg = parse_one(stream, global_char_env, escape_env, begin_stack)
    def eval_var(env) :
        e = arg.eval(env)
        if type(e) == StringToken :
            v = VariableToken(e.s)
            v.streamname = stream.name
            v.line = stream.row
            return v
        else :
            raise possible_error
    return LambdaToken(eval_var)

# for supporting \def{test}{arg}{got argument \var{arg}}
@global_token("def")
def def_token(stream, char_env, escape_env, begin_stack) :
    possible_error_name = stream.failure()
    name = parse_one(stream, char_env, escape_env, begin_stack)
    stream.read_while(" ")
    possible_error_args = stream.failure()
    args = parse_one(stream, char_env, escape_env, begin_stack)
    stream.read_while(" ")
    val = parse_one(stream, char_env, escape_env, begin_stack)
#    print "def args =",args,"val =",val
    # this is a LambdaToken for ultimately putting the definition into
    # the escape_env
    def eval_def(env) :
        try :
            n = name.eval(env)
        except AttributeError :
            raise possible_error_name.with_message("Cannot evaluate name for def.")
        if type(n) != StringToken :
            raise possible_error_name.with_message("Name for def must be string.")
        try :
            a = args.eval(env)
        except AttributeError :
            raise possible_error1.with_message("Cannot evaluate args for def.")
        if type(a) != StringToken :
            raise possible_error_name.with_message("Argument list for def must be string.")
        if a.s.strip() == "" :
            myargs = []
        else :
            myargs = [x.strip() for x in a.s.split(",")]
        # this is the handler which is put in the escape_env
        def this_def_handler(stream, char_env, escape_env, begin_stack) :
            arguments = dict()
            for a in myargs :
                arguments[a] = parse_one(stream, char_env, escape_env, begin_stack)
            # and this is what is executed when defined token is called
            def _this_def_handler(env) :
                env2 = dict()
                for key, value in env.iteritems() :
                    env2[key] = value
                for key, value in arguments.iteritems() :
                    env2[key] = value
                return val.eval(env2)
            return LambdaToken(_this_def_handler)
        escape_env[n.s] = this_def_handler
        return StringToken("")
    return LambdaToken(eval_def)

# for handling { and }
@global_char_handler('}')
def close_brace_handler(stream, char_env, escape_env, begin_stack) :
    raise stream.failure("Missing open brace for '}'.")

@global_char_handler('{')
def open_brace_handler(stream, char_env, escape_env, begin_stack) :
    possible_start_failure = stream.failure("Missing closing brace for '{'.")
    stream.read()
    if stream.peek() == '}' :
        stream.read()
        return StringToken("")
    begin_stack2 = begin_stack + ["{"]
    out = parse_one(stream, char_env, escape_env, begin_stack2)
    while stream.peek() != '}' :
        if stream.peek() == "" :
            raise possible_start_failure
        else :
            out += parse_one(stream, char_env, escape_env, begin_stack2)
    stream.read()
    return out

# for handling argument [ and ]'s
@global_char_handler(']')
def close_bracket_handler(stream, char_env, escape_env, begin_stack) :
    """Close brackets are normal text when not being used as an argument."""
    stream.read()
    return StringToken("]")

# this should be called when an [args] is necessary. See read_bracket_args
# @global_char_handler('[')
def open_bracket_handler(stream, char_env, escape_env, begin_stack) :
    possible_start_failure = stream.failure("Missing closing bracket for '['.")
    stream.read()
    if stream.peek() == ']' :
        stream.read()
        return ArgumentToken(StringToken(""))
    begin_stack2 = begin_stack + ["["]
    out = parse_one(stream, char_env, escape_env, begin_stack2)
    while stream.peek() != ']' :
        if stream.peek() == "" :
            raise possible_start_failure
        else :
            out += parse_one(stream, char_env, escape_env, begin_stack2)
    stream.read()
    return ArgumentToken(out)

# environments.
environment_handlers = dict()

@global_token("end")
def end_handler(stream, char_env, escape_env, begin_stack) :
    if begin_stack == [] :
        raise stream.failure("No environment to end.")
    name = parse_one(stream, global_char_env, escape_env, begin_stack)
    try :
        name = name.eval({})
    except AttributeError :
        raise stream.failure("Environment name must not be parameterized.")
    if type(name) != StringToken :
        raise stream.failure("Environment name must be a string.")
    if begin_stack[-1] != name.s :
        raise stream.failure("Environment "+repr(begin_stack[-1])+" cannot be closed by "+repr(name.s)+".")
    return EndEnvToken(name.s)

@global_token("begin")
def begin_handler(stream, char_env, escape_env, begin_stack) :
    name = parse_one(stream, global_char_env, escape_env, begin_stack)
    try :
        name = name.eval({})
    except AttributeError :
        raise stream.failure("Environment name must not be parameterized.")
    if type(name) != StringToken :
        raise stream.failure("Environment name must be a string.")
    name = name.s
    begin_stack2 = begin_stack + [name]
    (char_env2, escape_env2) = environment_handlers[name][0](stream, char_env, escape_env)
    token = parse_one(stream, char_env2, escape_env2, begin_stack2)
    if type(token) == lazytokens.EOFToken :
        raise stream.failure("Environment "+repr(name)+" has no end.")
    out = None
    while not (token == EndEnvToken(name)) :
        if type(token) == lazytokens.EOFToken :
            raise stream.failure("Environment "+repr(name)+" has no end.")
        if out == None :
            out = token
        else :
            out += token
        token = parse_one(stream, char_env2, escape_env2, begin_stack2)
    if out == None :
        return environment_handlers[name][1](char_env2, escape_env2, escape_env, StringToken(""))
    else : return environment_handlers[name][1](char_env2, escape_env2, escape_env, out)

# this is a helper for tokens which want a bracketed argument.  It
# parses a bracketed argument and returns its content, or returns none
# if there are no bracket args
def read_bracket_args(stream, char_env, escape_env, begin_stack) :
    if stream.peek() == "[" :
        args = open_bracket_handler(stream, char_env, escape_env, begin_stack)
        # returns an ArgumentToken
        return args.token
    else :
        return None

# for using normal lambdas.  f(bracket_arg, *args) if bargs, else f(*args)
def make_handler(nargs, bargs=False) :
    def transformer(f) :
        def handler(stream, char_env, escape_env, begin_stack) :
            if bargs :
                bracket_args = read_bracket_args(stream, char_env, escape_env, begin_stack)
            args = []
            for i in range(0, nargs) :
                a = parse_one(stream, char_env, escape_env, begin_stack)
                args.append(a)
            if bargs :
                return f(bracket_args.token, *args)
            else :
                return f(*args)
        return handler
    return transformer

@global_token("#")
@make_handler(0)
def hash_escape_handler() :
    return StringToken("#")

###
### external definitions of parsing beyond the core parser.
###
def insert_module(module) :
    for key, value in module.char_handlers.iteritems() :
        global_char_env[key] = value
    for key, value in module.token_handlers.iteritems() :
        global_tokens[key] = value
    for key, value in module.environment_handlers.iteritems() :
        environment_handlers[key] = value
import textmarkup
insert_module(textmarkup)
import references
insert_module(references)
import images
insert_module(images)
import filerefs
insert_module(filerefs)
import math
insert_module(math)

###
### handling knowing where we're outputting and inputting
###
def set_global_output_dir(dir) :
    global_tokens["_global_base_out_dir"] = os.path.abspath(dir)
    global_tokens["_curr_out_dir"] = os.path.abspath(dir)
def set_output_dir(dir, tenv=global_tokens) :
    tenv["_curr_out_dir"] = os.path.abspath(os.path.join(tenv["_global_base_out_dir"], dir))
    if os.path.relpath(tenv["_curr_out_dir"], tenv["_global_base_out_dir"]).startswith("..") :
        raise Exception("Going into directory "+repr(dir)+" which is not in global output directory "+repr(tenv["_global_base_out_dir"]))
@global_token("setoutputdir")
def setoutputdirhandler(stream, char_env, token_env, begin_stack) :
    dir = parse_one(stream, char_env, token_env, begin_stack)
    try :
        dir = dir.eval({})
    except AttributeError :
        raise Exception("Can't change to unexecutable directory name "+repr(dir)+".")
    if type(dir) == StringToken :
        set_output_dir(dir.s)
        return StringToken("")
    else :
        raise Exception("Can't change to non-string directory name "+repr(dir)+".")

def set_input_dir(dir) :
    global_tokens["_global_input_dir"] = os.path.abspath(dir)

global_tokens["_fluid_let"] = []

@global_token("include")
def include_handler(stream, char_env, token_env, begin_stack) :
    file = parse_one(stream, char_env, token_env, begin_stack)
    def _handler(env) :
        try :
            f = file.eval(env)
        except AttributeError :
            raise stream.failure("Can't evaluate file to include "+repr(file)+".")
        if type(f) == StringToken :
            filename = os.path.abspath(os.path.join(token_env["_global_input_dir"], f.s))
            if os.path.isfile(filename) :
                fluid_letted = dict()
                for name in token_env["_fluid_let"] :
                    fluid_letted[name] = token_env[name]
#                print "fluid",fluid_letted
                oldinpdir = token_env["_global_input_dir"]
                oldoutdir = token_env["_curr_out_dir"]
                token_env["_global_input_dir"] = os.path.split(filename)[0]
                ret = global_parse(streams.fileStream(filename))
                token_env["_curr_out_dir"] = oldoutdir
                token_env["_global_input_dir"] = oldinpdir
                for key,value in fluid_letted.iteritems() :
                    token_env[key] = value
                return ret
            else :
                raise stream.failure("No such file to include "+repr(filename)+".")
        else :
            raise stream.failure("Filename must be a string in include.")
    return LambdaToken(_handler)
