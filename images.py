# for including images

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

# handles \includegraphics[width=xxx,height=xxx,ext=xxx,alt=xxx]{filename}.
@add_token_handler(token_handlers, "includegraphics")
def includegraphics_handler(stream, char_env, token_env, begin_stack) :
    poss_err = stream.failure()
    barg = read_bracket_args(stream, char_env, token_env, begin_stack)
    filename = parse_one(stream, char_env, token_env, begin_stack)
    
    def _handler(env) :
        fn = filename.eval(env).s # brittle brittle brittle <<< vvv
        if barg is None :
            args = ""
        else :
            args = barg.eval(env).s

        fn2 = os.path.abspath(os.path.join(token_env["_global_input_dir"], fn))
        outdir = os.path.abspath(os.path.join(token_env["_curr_out_dir"], os.path.split(fn)[0]))
        args = [[x.strip() for x in y.split("=") if x.strip() != ""] for y in args.split(",")]
        args = [x for x in args if x != []]
#        print args
        args = dict(args)

#        print fn, outdir, args

        dimstring = ""
        altstring = args.get("alt","")
        
        width = args.get("width","")
        height = args.get("height","")
        ext = args.get("ext",None)
        page = args.get("page",None)

        if width == "" and height == "" and ext is None and page is None :
            outfile = os.path.join(outdir, os.path.split(fn)[1])
            if not os.path.isdir(os.path.split(outfile)[0]) :
                os.makedirs(os.path.split(outfile)[0], 0755)
            shutil.copy(fn2, outfile)
        else : # need to convert!
            pagemod = "" if page is None else ("["+str(page)+"]")
            pagemangle = "" if page is None else ("_p"+str(page)+"_")
            
            resize = width
            if height != "" :
                resize += "x"+height
            resize_arg = []
            if resize != "" :
                resize_arg = ["-resize",resize]
            r_mangle = "" if resize == "" else (resize + "_")

            outfile = os.path.join(outdir, r_mangle + pagemangle + os.path.split(fn)[1]) + ("" if ext is None else ("."+ext))
            if not os.path.isdir(os.path.split(outfile)[0]) :
                os.makedirs(os.path.split(outfile)[0], 0755)
            print "Converting",repr(fn2),"to",repr(outfile),
            if os.path.isfile(outfile) and os.path.getmtime(outfile) >= os.path.getmtime(fn2):
                print "... already converted."
            else :
                print ["convert", fn2, resize_arg, outfile]
                retcode = subprocess.call(["convert", fn2+pagemod] + resize_arg + [outfile])
                if retcode != 0 :
                    raise Exception("Retcode was "+str(retcode))
                print "... done"
        relout = os.path.relpath(outfile, token_env["_curr_out_dir"])
        return StringToken("<IMG ALT=\""+altstring+"\""+dimstring+"SRC=\""+relout+"\">")
    return LambdaToken(_handler)
