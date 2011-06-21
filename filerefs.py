# for referencing files

from lazytokens import (StringToken, LambdaToken, ListToken, VariableToken, SelfEvaluatingToken)
from parser import (make_handler, global_char_env, parse_one, parse_all, read_bracket_args)
from environments import (CharacterEnvironment, add_char_handler, add_token_handler)
import shutil
import os.path
import subprocess

# any module with macros needs to have these variables
char_handlers = dict()
token_handlers = dict()
environment_handlers = dict()

# handles \file[link name]{filename}.
@add_token_handler(token_handlers, "file")
def fileref_handler(stream, char_env, token_env, begin_stack) :
    poss_err = stream.failure()
    barg = read_bracket_args(stream, char_env, token_env, begin_stack)
    filename = parse_one(stream, char_env, token_env, begin_stack)
    
    def _handler(env) :
        fn = filename.eval(env).s # brittle brittle brittle <<< vvv
        if barg is None :
            linktext = os.path.split(fn)[1]
        else :
            linktext = barg.eval(env).s

        fn2 = os.path.abspath(os.path.join(token_env["_global_input_dir"], fn))
        outfile = os.path.abspath(os.path.join(token_env["_curr_out_dir"], fn))
        
        print "Copying",repr(fn2),"to",repr(outfile),
        
        if not os.path.isdir(os.path.split(outfile)[0]) :
            os.makedirs(os.path.split(outfile)[0], 0755)
        
        if os.path.isfile(outfile) and os.path.getmtime(outfile) >= os.path.getmtime(fn2):
            print "... already copied."
        else :
            print
            shutil.copy(fn2, outfile)
        
        relout = os.path.relpath(outfile, token_env["_curr_out_dir"])
        return StringToken("<A HREF=\""+relout+"\">"+linktext+"</A>")
    
    return LambdaToken(_handler)
