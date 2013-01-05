# math.py
# handles math mode!

# for more information on handling html math stuff see
# http://www.cs.tut.fi/~jkorpela/math/

from lazytokens import (StringToken, LambdaToken, ListToken, VariableToken, SelfEvaluatingToken, Token, ParagraphToken, InhibitParagraphToken, ColumnBreakToken, LineBreakToken)
from parser import (make_handler, global_char_env, parse_one, parse_all, read_bracket_args, open_brace_handler)
from environments import (CharacterEnvironment, add_char_handler, add_token_handler)
import string

# any module with macros needs to have these variables
char_handlers = dict()
token_handlers = dict()
environment_handlers = dict()

math_char_env = CharacterEnvironment({}, global_char_env)

class MathToken(Token) :
    def eval(self, env) :
        return self
    def render(self, env) :
        self.fail("Math token "+repr(self)+" has not implemented a render method.")

class MathNoToken(MathToken) :
    pass

class MathPassThroughToken(MathToken) :
    def __init__(self, obj) :
        self.obj = obj
    def render(self, env) :
        return render_math(self.obj, env)

class MathOrdToken(MathToken) :
    def __init__(self, stream, display_text) :
        Token.__init__(self, stream)
        self.display_text = display_text
    def __repr__(self) :
        return "<MathOrdToken "+repr(self.display_text)+">"
    def render(self, env) :
        return StringToken(self.display_text)

class MathOpToken(MathToken) :
    def __init__(self, stream, display_text) :
        Token.__init__(self, stream)
        self.display_text = display_text
        self.trailingspace = " "
    def __repr__(self) :
        return "<MathOpToken "+repr(self.display_text)+">"
    def render(self, env) :
        return StringToken(self.display_text)+StringToken(self.trailingspace)

class MathBraceStartToken(MathToken) :
    """See math_open_brace_handler."""

class MathBinToken(MathToken) :
    def __init__(self, stream, display_text) :
        Token.__init__(self, stream)
        self.display_text = display_text
    def __repr__(self) :
        return "<MathBinToken "+repr(self.display_text)+">"
    def render(self, env) :
        return StringToken(" "+self.display_text+" ")
    def coerce_down(self) : # takes a binary operator and coerces it into a prefix operator
        t = MathOpToken(None, self.display_text)
        t.streamerr = self.streamerr
        t.trailingspace = "" # no trailing space for a coerced binary operator
        return t

class MathRelToken(MathToken) :
    def __init__(self, stream, display_text) :
        Token.__init__(self, stream)
        self.display_text = display_text
    def __repr__(self) :
        return "<MathRelToken "+repr(self.display_text)+">"
    def render(self, env) :
        return StringToken("&ensp;"+self.display_text+"&ensp;")

class MathOpenToken(MathToken) :
    def __init__(self, stream, display_text) :
        Token.__init__(self, stream)
        self.display_text = display_text
        self.insides = None
        self.close = None
    def __repr__(self) :
        return ("<MathOpenToken "+repr(self.display_text)
                +" insides:"+repr(self.insides)+" close:"+repr(self.close)+">")
    def eval(self, env) :
        insides = self.insides.eval(env)
        close = self.close.eval(env)
        new = MathOpenToken(None, self.display_text)
        new.streamerr = self.streamerr
        new.insides = insides
        new.close = close
        return new
    def render(self, env) :
        if self.insides == None :
            self.insides = StringToken("")
        if self.close == None :
            self.fail("Missing closing delimeter to match "+repr(self)+".")
        return (StringToken(self.display_text) + render_math(self.insides, env) + render_math(self.close, env))

class MathCloseToken(MathToken) :
    def __init__(self, stream, display_text) :
        Token.__init__(self, stream)
        self.display_text = display_text
    def __repr__(self) :
        return "<MathOpenToken "+repr(self.display_text)+">"
    def render(self, env) :
        return StringToken(self.display_text)

@add_char_handler(math_char_env, '{')
def math_open_brace_handler(stream, char_env, escape_env, begin_stack) :
    t = MathBraceStartToken(stream)
    return t + open_brace_handler(stream, char_env, escape_env, begin_stack)

###
### for handling defining
###
@add_token_handler(token_handlers, 'math')
def unrendered_math_handler(stream, char_env, escape_env, begin_stack) :
    out = parse_one(stream, math_char_env, escape_env, begin_stack)
    return out

###
### handling inline $...$
###

@add_char_handler(char_handlers, '$')
def inline_math_handler(stream, char_env, escape_env, begin_stack) :
    possible_start_failure = stream.failure("Missing closing '$ for math mode.")
    stream.read()
    if stream.peek() == '$' :
        raise possible_start_failure.with_message("Math mode '$$' is empty.")
    begin_stack2 = begin_stack + ["$"]
    out = parse_one(stream, math_char_env, escape_env, begin_stack2)
    while stream.peek() != '$' :
        if stream.peek() == "" :
            raise possible_start_failure
        else :
            out += parse_one(stream, math_char_env, escape_env, begin_stack2)
    stream.read() # read the final '$'
    return make_render_math(out)

# but still wanna write $ sometimes
@add_token_handler(token_handlers, '$')
def escape_dollar_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken("$")


###
### handling \begin{equation*}...\end{equation*}
###
def begin_equation_s_environment(stream, char_env, token_env) :
    return (math_char_env, token_env)
def end_equation_s_environment(char_env, escape_env, outer_token_env, out) :
    return ParagraphToken() + InhibitParagraphToken() + (StringToken("<CENTER>") + make_render_math(out) + StringToken("</CENTER>\n")) + ParagraphToken()
# the following forgets to create a paragraph break after the math
#    return InhibitParagraphToken()+StringToken("<CENTER>") + make_render_math(out) + StringToken("</CENTER>\n")
environment_handlers["equation*"] = (begin_equation_s_environment, end_equation_s_environment)


###
### handling \begin{align*}...\end{align*}
###
def begin_aligns_environment(stream, char_env, token_env) :
    return (math_char_env, token_env)
def end_aligns_environment(char_env, escape_env, outer_token_env, out) :
    return InhibitParagraphToken()+StringToken("<CENTER>") + out + StringToken("</CENTER>\n")
environment_handlers["align*"] = (begin_aligns_environment, end_aligns_environment)

###
### matrices
###
def begin_matrix_environment(stream, char_env, token_env) :
    def col_break_handler(stream, char_env, escape_env, begin_stack) :
        stream.read()
        return ColumnBreakToken()
    return (math_char_env.extend({"&" : col_break_handler}),
            token_env)
def end_matrix_environment(char_env, escape_env, outer_token_env, out) :
    table = StringToken("<TABLE CLASS=\"mathmatrix\">\n")
    if type(out) is ListToken :
        inrow = False
        incolumn = False
        for token in out.tokens :
            if type(token) is LineBreakToken :
                if incolumn :
                    table += StringToken("</TD>")
                if inrow :
                    table += StringToken("</TR>\n")
                else :
                    token.fail("Line break in matrix for no elements.")
                inrow = False
                incolumn = False
            elif type(token) is ColumnBreakToken :
                if incolumn :
                    table += StringToken("</TD>")
                incolumn = False
            else :
                if not inrow :
                    table += StringToken("<TR>")
                if not incolumn :
                    table += StringToken("<TD>")
                inrow = True
                incolumn = True
                table += token
        if incolumn :
            table += StringToken("</TD>")
        if inrow :
            table += StringToken("</TR>\n")
    else :
        table += StringToken("<TR><TD>")+out+StringToken("</TD></TR>")
    table += StringToken("</TABLE>")
    print "table",table
    return MathPassThroughToken(table)
environment_handlers["matrix"] = (begin_matrix_environment, end_matrix_environment)

def begin_pmatrix_environment(stream, char_env, token_env) :
    return begin_matrix_environment(stream, char_env, token_env)
def end_pmatrix_environment(char_env, escape_env, outer_token_env, out) :
    t = MathOpenToken(None, '(')
    t.insides = end_matrix_environment(char_env, escape_env, outer_token_env, out)
    t.close = MathCloseToken(None, ')')
    return t
environment_handlers["pmatrix"] = (begin_pmatrix_environment, end_pmatrix_environment)

###
### Fractions
###

@add_token_handler(token_handlers, "frac")
def math_frac_handler(stream, char_env, token_env, begin_stack) :
    num = parse_one(stream, char_env, token_env, begin_stack)
    denom = parse_one(stream, char_env, token_env, begin_stack)
    table = StringToken('<TABLE CLASS="mathfrac"><TR CLASS="mathfracnum"><TD>')
    table += num + StringToken("</TD></TR><TR><TD>") + denom + StringToken("</TD></TR></TABLE>")
    return MathPassThroughToken(table)


# main renderer

def render_math(math_tokens, env) :
#    print "* render_math *",math_tokens
    mts = math_tokens.eval(env)
#    print "* render_math evaled *",mts
    if isinstance(mts, MathToken) :
        if type(mts) == MathBinToken :
            return mts.coerce_down().render(env)
        elif type(mts) == MathBraceStartToken or type(mts) == MathNoToken :
            return StringToken("")
        elif isinstance(mts, MathToken) :
            return mts.render(env)
        else :
            mts.fail("Non-math token "+repr(mts)+" found in math mode.")
    elif type(mts) is ListToken :
        out = StringToken("")
        first = True
        for t in mts.tokens :
            if type(t) == MathBraceStartToken :
                first = True
            elif type(t) == MathNoToken :
                pass # just ignore it
            elif isinstance(t, MathToken) :
                if first and type(t) == MathBinToken :
                    t = t.coerce_down()
                out += t.render(env)
                first = False
            elif type(t) == StringToken :
                out += t #MathOrdToken(t.streamerr, t.s)
            else :
                mts.fail("Non-math token "+repr(t)+" found in math mode.")
#        print "* rendered *",out
        return out
    else :
        return mts

class MathRenderToken(Token) :
    """A token from which the math stuff can be retrieved, but when
    evaled does the rendering."""
    def __init__(self, math) :
        Token.__init__(self, None)
        self.math = math
    def eval(self, env) :
#        print "math",self.math
        return render_math(self.math, env).eval(env)

# makes a handler for these tokens
def make_render_math(math_tokens) :
    return MathRenderToken(math_tokens)

###
### spaces
###

# eat spaces
@add_char_handler(math_char_env, " ")
@add_char_handler(math_char_env, "\t")
@add_char_handler(math_char_env, "\n")
def space_handler(stream, char_env, escape_env, begin_stack) :
    stream.read()
    return MathNoToken(stream)

# but provide escaping spaces (this is global)
@add_token_handler(token_handlers, " ") # normal space
def space_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken(" ")

@add_token_handler(token_handlers, ",") # thin space
@add_token_handler(token_handlers, "thinspace")
def space_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken("&#8202;")

@add_token_handler(token_handlers, ":")
@add_token_handler(token_handlers, "midspace")
def space_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken("&thinsp;")

@add_token_handler(token_handlers, "quad")
def space_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken("&nbsp;&nbsp;&nbsp;&nbsp;") # <- maybe not the right way to do this?

###
### Positioning
###

class MathSupToken(MathToken) :
    def __init__(self, obj) :
        MathToken.__init__(self, None)
        self.streamerr = obj.streamerr
        self.supscript_obj = obj
    def render(self, env) :
        return (StringToken("<sup>")
                +render_math(MathBraceStartToken(None)+self.supscript_obj, env)
                +StringToken("</sup>"))

class MathSubToken(MathToken) :
    def __init__(self, obj) :
        MathToken.__init__(self, None)
        self.streamerr = obj.streamerr
        self.subscript_obj = obj
    def render(self, env) :
        return (StringToken("<sub>")
                +render_math(MathBraceStartToken(None)+self.subscript_obj, env)
                +StringToken("</sub>"))

@add_char_handler(math_char_env, "^")
def sup_handler(stream, char_env, escape_env, begin_stack) :
    stream.read()
    t = parse_one(stream, char_env, escape_env, begin_stack)
    return MathSupToken(t)

@add_char_handler(math_char_env, "_")
def sup_handler(stream, char_env, escape_env, begin_stack) :
    stream.read()
    t = parse_one(stream, char_env, escape_env, begin_stack)
    return MathSubToken(t)

###
### Type 0 symbols (ordinary)
###

# these are characters which are like nouns (variables and numbers)

def _make_mathord_handler(display_text, token=True) : # token=False if it's a char handler
    def _handler(stream, char_handlers, escape_env, begin_stack) :
        if not token :
            stream.read()
        return MathOrdToken(stream, display_text)
    return _handler

# numbers are just the number
for i in range(0, 10) :
    math_char_env[str(i)] = _make_mathord_handler(str(i), False)

# a-zA-Z are variablefied
for c in string.ascii_letters :
    math_char_env[c] = _make_mathord_handler("<var>"+c+"</var>", False)

def make_token_type0_symbol(symboldict, var=False) :
    for key, value in symboldict.iteritems() :
        if var :
            token_handlers[key] = _make_mathord_handler("<var>"+value+"</var>")
        else :
            token_handlers[key] = _make_mathord_handler(value)

def make_token_type0(symboldict) :
    for key, value in symboldict.iteritems() :
        math_char_env[key] = _make_mathord_handler(value, False)

_upper_greek = dict({"Gamma" : "&Gamma;",
                     "Delta" : "&Delta;",
                     "Lambda" : "&Lambda;",
                     "Phi" : "&Phi;",
                     "Pi" : "&Pi;",
                     "Psi" : "&Psi;",
                     "Sigma" : "&Sigma;",
                     "Theta" : "&Theta;",
                     "Upsilon" : "&Upsilon;",
                     "Xi" : "&Xi;",
                     "Omega" : "&Omega;"})
_lower_greek = dict({"alpha" : "&alpha;",
                     "beta" : "&beta;",
                     "gamma" : "&gamma;",
                     "delta" : "&delta;",
                     "epsilon" : "&epsilon;",
                     "zeta" : "&zeta;",
                     "eta" : "&eta;",
                     "theta" : "&theta;",
                     "iota" : "&iota;",
                     "kappa" : "&kappa;",
                     "lambda" : "&lambda;",
                     "mu" : "&mu;",
                     "nu" : "&nu;",
                     "xi" : "&xi;",
                     "pi" : "&pi;",
                     "rho" : "&rho;",
                     "sigma" : "&sigma;",
                     "tau" : "&tau;",
                     "upsilon" : "&upsilon;",
                     "phi" : "&phi;",
                     "chi" : "&chi;",
                     "psi" : "&psi;",
                     "omega" : "&omega;"})
make_token_type0_symbol(_upper_greek, False)
make_token_type0_symbol(_lower_greek, True)

_other_symbols = dict({"'": "&thinsp;&prime;",
                       ',': ",&thinsp;",
                       })
make_token_type0(_other_symbols)

_other_symbol_tokens = dict({"circ": "&deg;",
                             "infty": "&infin;",
                             "qed": "&#x220e;",
                             })
make_token_type0_symbol(_other_symbol_tokens)

###
### Type 1 symbols (operators)
###

def _make_mathop_handler(display_text, token=True) : # token=False if it's a char handler
    def _handler(stream, char_handlers, escape_env, begin_stack) :
        if not token :
            stream.read()
        return MathOpToken(stream, display_text)
    return _handler

def make_type1_token(symboldict) :
    for key, value in symboldict.iteritems() :
        token_handlers[key] = _make_mathop_handler(value, True)

_math_ops = dict({'arccos' : 'arccos',
                  'arcsin' : 'arcsin',
                  'arctan' : 'arctan',
                  'arg' : 'arg',
                  'cos' : 'cos',
                  'cosh' : 'cosh',
                  'cot' : 'cot',
                  'coth' : 'coth',
                  'csc' : 'csc',
                  'deg' : 'deg',
                  'det' : 'det',
                  'dim' : 'dim',
                  'exp' : 'exp',
                  'gcd' : 'gcd',
                  'hom' : 'hom',
                  'inf' : 'inf',
                  'injlim' : 'inj&thinsp;lim',
                  'ker' : 'ker',
                  'lg' : 'lg',
                  'lim' : 'lim',
                  'liminf' : 'lim&thinsp;inf',
                  'limsup' : 'lim&thinsp;sup',
                  'ln' : 'ln',
                  'log' : 'log',
                  'max' : 'max',
                  'min' : 'min',
                  'Pr' : 'Pr',
                  'projlim' : 'proj&thinsp;lim',
                  'sec' : 'sec',
                  'sin' : 'sin',
                  'sinh' : 'sinh',
                  'sup' : 'sup',
                  'tan' : 'tan',
                  'tanh' : 'tanh'
                  })
make_type1_token(_math_ops)

###
### Type 2 symbols (binary operators)
###

def _make_mathbin_handler(display_text, token=True) : # token=False if it's a char handler
    def _handler(stream, char_handlers, escape_env, begin_stack) :
        if not token :
            stream.read()
        return MathBinToken(stream, display_text)
    return _handler

def make_type2_symbol(symboldict) :
    for key, value in symboldict.iteritems() :
        math_char_env[key] = _make_mathbin_handler(value, False)

def make_type2_token(symboldict) :
    for key, value in symboldict.iteritems() :
        token_handlers[key] = _make_mathbin_handler(value, True)

_math_bin_ops = dict({'+' : '+',
                      '-' : '&minus;',
                      '*' : '*'})
make_type2_symbol(_math_bin_ops)

_math_bin_token_ops = dict({'cdot' : '&sdot;',
                            'times' : '&times;',
                            'pm' : '&plusmn;',
                            'cup': '&cup;',
                            'cap': '&cap;',
                            })
make_type2_token(_math_bin_token_ops)

###
### Type 3 symbols (relations)
###

def _make_mathrel_handler(display_text, token=True) : # token=False if it's a char handler
    def _handler(stream, char_handlers, escape_env, begin_stack) :
        if not token :
            stream.read()
        return MathRelToken(stream, display_text)
    return _handler

def make_type3_symbol(symboldict) :
    for key, value in symboldict.iteritems() :
        math_char_env[key] = _make_mathrel_handler(value, False)

def make_type3_token(symboldict) :
    for key, value in symboldict.iteritems() :
        token_handlers[key] = _make_mathrel_handler(value, True)

_math_rel_ops = dict({'=': '=',
                      '<': '&lt;',
                      '>': '&gt;',
                      ':': ':'
                      })
make_type3_symbol(_math_rel_ops)

_math_rel_token_ops = dict({'leq': '&le;',
                            'geq': '&ge;',
                            'neq': '&ne;',
                            'equiv': '&equiv;',
                            'approx': '&asymp;',
                            'in': '&isin;',
                            'subset': '&sub;',
                            'supset': '&sup;',
                            'to': '&rarr;',
                            'rightarrow' : '&rarr;',
                            'leftarrow' : '&larr;',
                            'botharrow' : '&harr;',
                            'leftrightarrows' : '&#8646;'
                            })
make_type3_token(_math_rel_token_ops)

###
### Type 4 symbols (left/opening delimeters)
###

def _make_mathopen_handler(display_text, token=True) : # token=False if it's a char handler
    def _handler(stream, char_handlers, escape_env, begin_stack) :
        if not token :
            stream.read()
        o = MathOpenToken(stream, display_text)
        if stream.peek() == "$" :
            raise stream.failure("No closing delimiter for "+repr(o)+".")
        insides = None
        t = parse_one(stream, char_handlers, escape_env, begin_stack)
        while type(t) != MathCloseToken :
            if stream.peek() == "$" :
                raise stream.failure("No closing delimiter for "+repr(o)+".")
            elif insides == None :
                insides = t
            else :
                insides += t
            t = parse_one(stream, char_handlers, escape_env, begin_stack)
        o.insides = MathBraceStartToken(stream) + insides
        o.close = t
        return o
    return _handler

def make_type4_symbol(symboldict) :
    for key, value in symboldict.iteritems() :
        math_char_env[key] = _make_mathopen_handler(value, False)

def make_type4_token(symboldict) :
    for key, value in symboldict.iteritems() :
        token_handlers[key] = _make_mathopen_handler(value, True)

_math_open_symbols = dict({'(': '(',
                           '[': '[',
                           })
make_type4_symbol(_math_open_symbols)

_math_open_tokens = dict({'{': '{',
                          })
make_type4_token(_math_open_tokens)


# hacks!!!
@add_token_handler(token_handlers, "left")
def math_left_handler(stream, char_handlers, escape_env, begin_stack) :
    return _make_mathopen_handler("<span class=\"mathleftdelim\">" + stream.read() + "</span>")(stream, char_handlers, escape_env, begin_stack)

@add_token_handler(token_handlers, "bigleft")
def math_left_handler(stream, char_handlers, escape_env, begin_stack) :
    return _make_mathopen_handler("<span class=\"mathbigleftdelim\">" + stream.read() + "</span>")(stream, char_handlers, escape_env, begin_stack)



###
### Type 5 symbols (right/closing delimiters)
###

def _make_mathclose_handler(display_text, token=True) : # token=False if it's a char handler
    def _handler(stream, char_handlers, escape_env, begin_stack) :
        if not token :
            stream.read()
        return MathCloseToken(stream, display_text)
    return _handler

def make_type5_symbol(symboldict) :
    for key, value in symboldict.iteritems() :
        math_char_env[key] = _make_mathclose_handler(value, False)

def make_type5_token(symboldict) :
    for key, value in symboldict.iteritems() :
        token_handlers[key] = _make_mathclose_handler(value, True)

_math_close_symbols = dict({')': ')',
                            ']': ']',
                            })
make_type5_symbol(_math_close_symbols)

_math_close_tokens = dict({'}': '}',
                           })
make_type5_token(_math_close_tokens)

# hacks!!!
@add_token_handler(token_handlers, "right")
def math_right_handler(stream, char_handlers, escape_env, begin_stack) :
    d = stream.read()
    if d == "." :
        d = ""
    else :
        d = "<span class=\"mathrightdelim\">" + d + "</span>"
    return MathCloseToken(stream, d)
@add_token_handler(token_handlers, "bigright")
def math_right_handler(stream, char_handlers, escape_env, begin_stack) :
    d = stream.read()
    if d == "." :
        d = ""
    else :
        d = "<span class=\"mathbigrightdelim\">" + d + "</span>"
    return MathCloseToken(stream, d)


###
### Fonts
###

@add_token_handler(token_handlers, "text")
@add_token_handler(token_handlers, "mathrm")
def math_rm_handler(stream, char_env, token_env, begin_stack) :
    charenv2 = char_env.extend({})
    for c in string.ascii_letters :
        charenv2[c] = _make_mathord_handler(c, False)
    return parse_one(stream, charenv2, token_env, begin_stack)

@add_token_handler(token_handlers, "mathbf")
def math_bf_handler(stream, char_env, token_env, begin_stack) :
    charenv2 = char_env.extend({})
    for c in string.ascii_letters :
        charenv2[c] = _make_mathord_handler("<b>"+c+"</b>", False)
    return parse_one(stream, charenv2, token_env, begin_stack)

@add_token_handler(token_handlers, "mathit")
def math_it_handler(stream, char_env, token_env, begin_stack) :
    charenv2 = char_env.extend({})
    for c in string.ascii_letters :
        charenv2[c] = _make_mathord_handler("<i>"+c+"</i>", False)
    return parse_one(stream, charenv2, token_env, begin_stack)

mathbb_dict = dict({'R' : '&#8477;',
                    'C' : '&#8450;',
                    'N' : '&#8469;',
                    'P' : '&#8473;',
                    'Q' : '&#8474;',
                    'Z' : '&#8484;',
                    })

@add_token_handler(token_handlers, "mathbb")
def math_bb_handler(stream, char_env, token_env, begin_stack) :
    charenv2 = char_env.extend({})
    for c,ent in mathbb_dict.iteritems() :
        charenv2[c] = _make_mathord_handler(ent, False)
    return parse_one(stream, charenv2, token_env, begin_stack)
