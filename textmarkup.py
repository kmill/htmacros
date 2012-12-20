# textmarkup.py
#
# for handling plain text and its fonts, formatting, etc.

from lazytokens import (StringToken, LambdaToken, ListToken, VariableToken, SelfEvaluatingToken, EndEnvToken)
from lazytokens import (ParagraphToken, InhibitParagraphToken, ItemToken, LineBreakToken, ColumnBreakToken, HorizontalLineToken)
from environments import (DefaultCharacterEnvironment, CharacterEnvironment, add_char_handler, add_token_handler)
from parser import (make_handler, global_char_env, parse_one, parse_all, read_bracket_args)
from references import (add_counter, get_counter, set_page_reference, set_anchor_reference, make_reference, make_label)
from references import (generate_id, get_anchor_by_id, counters_to_string, get_autoname_by_ref_name)
from streams import fileStream
import shutil
import os.path

# any module with macros needs to have these variables
char_handlers = dict()
token_handlers = dict()
environment_handlers = dict()

###
### Fonts
###

def html_handler(tokenname, html) :
    @add_token_handler(token_handlers, tokenname)
    @make_handler(1)
    def _handler(inside) :
        return StringToken("<"+html+">") + inside + StringToken("</"+html+">")
    return _handler

textit = html_handler("textit", "I")
textbf = html_handler("textbf", "B")
texttt = html_handler("texttt", "TT")
textsc = html_handler("textsc", "SPAN STYLE=\"font-variant: small-caps;\" CLASS=\"small-caps\"")

@add_token_handler(token_handlers, "emph")
def emph_handler(stream, char_env, token_env, begin_stack) :
    try :
        in_emph = token_env["_in_emph"]
    except KeyError :
        in_emph = False
    emphed = parse_one(stream, char_env, token_env.extend({"_in_emph" : not in_emph}), begin_stack)
    if in_emph :
        return StringToken("<SPAN CLASS=\"de_em\">") + emphed + StringToken("</SPAN>")
    else :
        return StringToken("<EM>") + emphed + StringToken("</EM>")

###
### Breaks
###

@add_token_handler(token_handlers, "\\")
def line_break_handler(stream, char_env, token_env, begin_stack) :
    return LineBreakToken()

@add_token_handler(token_handlers, "hline")
def horizontal_line_handler(stream, char_env, token_handlers, begin_stack) :
    return HorizontalLineToken()

###
### Accents
###

def make_accent_handler(token, html_postfix) :
    def _handler(char) :
        def __handler(env) :
            c = char.eval(env).s[0]
            return StringToken("&"+c+html_postfix+";")
        return LambdaToken(__handler)
    return add_token_handler(token_handlers, token)(make_handler(1)(_handler))

make_accent_handler('`', 'grave')
make_accent_handler('\'', 'acute')
make_accent_handler('^', 'circ')
make_accent_handler('"', 'uml')
make_accent_handler('~', 'tilde')
make_accent_handler('r', 'ring')
make_accent_handler('c', 'cedil')

###
### Special symbols
###

def make_spec_char_handler(token, html_entity) :
    def _handler() :
        return StringToken(html_entity)
    return add_token_handler(token_handlers, token)(make_handler(0)(_handler))

make_spec_char_handler('copyright', '&copy;')
make_spec_char_handler('nbsp', '&nbsp;')

@add_token_handler(token_handlers, "char")
@make_handler(1)
def char_handler(inside) :
    return StringToken("&")+inside+StringToken(";")

###
### Text prettification
###

char_pretty_text = CharacterEnvironment({}, global_char_env)

@add_char_handler(char_pretty_text, '`')
def open_quote_handler(stream, char_env, token_env, begin_stack) :
    stream.read()
    if stream.peek() == '`' :
        stream.read()
        return StringToken("&ldquo;")
    else :
        return StringToken("&lsquo;")

@add_char_handler(char_pretty_text, '\'')
def close_quote_handler(stream, char_env, token_env, begin_stack) :
    stream.read()
    if stream.peek() == '\'' :
        stream.read()
        return StringToken("&rdquo;")
    else :
        return StringToken("&rsquo;")

@add_char_handler(char_pretty_text, '\n')
def newline_handler(stream, char_env, token_env, begin_stack) :
    t = stream.read_while(" \n")
    if len(t.split("\n")) >= 3 :
        return ParagraphToken()
    else :
        return StringToken(t)

# This code not to be used. Need \' for accents.
# sometimes I just wanna type '
#@add_token_handler(token_handlers, '\'')
#def escape_tick_handler(stream, char_env, token_env, begin_stack) :
#    return StringToken("'")

@add_char_handler(char_pretty_text, '-')
def close_quote_handler(stream, char_env, token_env, begin_stack) :
    stream.read()
    if stream.peek() == '-' :
        stream.read()
        if stream.peek() == '-' :
            stream.read()
            return StringToken("&mdash;")
        else :
            return StringToken("&ndash;")
    else :
        return StringToken("-")

_page_filenames = []

# \begin{page} ... \end{page} switches to pretty mode and does
# paragraphing, among other things like setting up labels.
def begin_page_environment(stream, char_env, escape_env) :
    file = parse_one(stream, char_env, escape_env, [])
    try :
        file = file.eval({})
    except AttributeError :
        raise stream.failure("Page file name must not be parameterized.")
    if type(file) != StringToken :
        raise stream.failure("File name must be a string.")
    
    get_counter("page").increment()
    pageid = generate_id("page", get_counter("page"))
    escape_env["_curr_pageid"] = pageid
    add_counter("footnote")

    set_page_reference(escape_env, pageid, file.s)
    return (char_pretty_text,
            escape_env.extend({"_page_footnotes" : []}))
def end_page_environment(char_env, token_env, outer_token_env, out) :
    def eval_footnotes(footnotes) :
        oldlenfoot = 0
        lenfoot = 0
        fout = StringToken("")
        while len(footnotes) > lenfoot :
            oldlenfoot = lenfoot
            lenfoot = len(footnotes)
            out = StringToken("")
            for (num, (id, footnote)) in zip(xrange(oldlenfoot+1,lenfoot+1), footnotes[oldlenfoot:lenfoot]) :
                make_label(token_env, id, id, StringToken("[%d]" % num))
                
                out += HorizontalLineToken() + InhibitParagraphToken() + get_anchor_by_id(id) \
                    + InhibitParagraphToken() \
                    + StringToken("<div class=\"footnote\">\n<sup>") \
                    + make_reference(token_env, StringToken("#ref_" + id), StringToken("[%d]" % num)) \
                    + StringToken("</sup> ") \
                    + footnote \
                    + StringToken("</div>\n")
            fout += out.eval({})
        return fout
    if token_env.has_key("_page_template") :
        out2 = out.eval({})
        if token_env["_page_footnotes"] :
            out2 += eval_footnotes(token_env["_page_footnotes"])
        rout = render_paragraphing(InhibitParagraphToken()+out2)
        if False : # set to True to debug render_paragraphing
            print "out =",out
            print
            print "rout =",rout
            print
        pageref = token_env["_curr_page_reference"]
        if not os.path.isdir(pageref.dir) :
            os.makedirs(pageref.dir, 0755)
        pagepath = pageref.path()
        if pagepath in _page_filenames :
            raise Exception("Two pages have the same filename "+repr(pagepath))
        _page_filenames.append(pagepath)
        css = StringToken("")
        if token_env.has_key("_page_css") :
            css = StringToken("<LINK REL=\"stylesheet\" HREF=\""
                              +os.path.relpath(token_env["_page_css"], os.path.split(pagepath)[0])
                              +"\" TYPE=\"text/css\">")
        if not token_env.has_key("_page_modified") :
            raise Exception("Page "+repr(pagepath)+" must have \\modified token.")
        # breadcrumbs:
        mybc = [(a[1], a[0], make_reference(token_env, a[1], a[0])) for a in token_env.get("_breadcrumbs", [])]
        def _get_name(overridename, label) :
            print "_getname", overridename, label
            if overridename is not None :
                return overridename
            else :
                return get_autoname_by_ref_name(label)
        if len(mybc) == 0 :
            breadcrumbs = pageref.autoname
        else :
            if mybc[0][0].s == pageref.labelname :
                breadcrumbs = _get_name(mybc[0][1], mybc[0][0])
            else :
                breadcrumbs = mybc[0][2]
            for crumb in mybc[1:] :
                breadcrumbs += StringToken(" > ")
                if crumb[0].s == pageref.labelname :
                    breadcrumbs += _get_name(crumb[1], crumb[0].s)
                else :
                    breadcrumbs += crumb[2]
            if token_env["_breadcrumbs"][-1][1].s != pageref.labelname :
                breadcrumbs += StringToken(" > ") + pageref.autoname
        # make page now
        pagetoken = token_env["_page_template"].eval({"pagetitle": token_env["_page_title"],
                                                      "pagecontent" : rout,
                                                      "css" : css,
                                                      "pagemodified" : token_env["_page_modified"],
                                                      "breadcrumbs" : breadcrumbs.eval({})})
        if type(pagetoken) == StringToken :
            f = open(pagepath, "w")
            f.write(pagetoken.s)
            f.close()
            print "Wrote page",pagepath
            return StringToken("")
        else :
            print "Token which caused error: ",pagetoken
            raise Exception("Page not a single string.")
    else :
        raise Exception("No page template has been specified to make pages.")
environment_handlers["page"] = (begin_page_environment, end_page_environment)

# Sets the title of the current page.
@add_token_handler(token_handlers, "title")
def title_handler(stream, char_env, token_env, begin_stack) :
    title = parse_one(stream, char_env, token_env, begin_stack)
    possible_error = stream.failure()
    def _handler(env) :
        if token_env.has_key("_page_title") :
            raise possible_error.with_message("Page has two titles.")
        title2 = title.eval(env)
        token_env["_page_title"] = title2
        if token_env.has_key("_curr_page_reference") :
            token_env["_curr_page_reference"].autoname = title2
        else :
            raise stream.failure("No page for title.")
#        return StringToken("<H1>")+title+StringToken("</H1>") + InhibitParagraphToken()
        return StringToken("")
    return LambdaToken(_handler)

# Sets the modified date of the current page.
@add_token_handler(token_handlers, "modified")
def modified_handler(stream, char_env, token_env, begin_stack) :
    modified = parse_one(stream, char_env, token_env, begin_stack)
    def _handler(env) :
        token_env["_page_modified"] = modified
        return StringToken("")
    return LambdaToken(_handler)

@add_token_handler(token_handlers, "footnote")
def footnote_handler(stream, char_env, token_env, begin_stack) :
    footnote = parse_one(stream, char_env, token_env, begin_stack)
    def _handler(env) :
        if not token_env.has_key("_page_footnotes") :
            raise stream.failure("Footnotes can only appear within a page")
        get_counter("footnote").increment()
        id = generate_id("footnote", get_counter("page"), get_counter("footnote"))
        make_label(token_env, "ref_"+id, "ref_"+id, "^")
        token_env["_page_footnotes"].append((id, footnote))
        return get_anchor_by_id("ref_"+id) + StringToken("<sup>") \
            + make_reference(token_env, StringToken("#" + id), None) \
            + StringToken("</sup>")
    return LambdaToken(_handler)

# takes a (list) token and handles ParagraphToken, InhibitParagraphToken, and LineBreakToken
def render_paragraphing(tokens) :
    if type(tokens) == StringToken :
        return tokens # if it's just a simple string with no newlines, don't wrap it in P tag
    elif type(tokens) != ListToken :
        return StringToken("")
    else :
        rendered_out = StringToken("")
        in_paragraph = False
        inhibit_paragraph = False
        for token in tokens.tokens :
            if type(token) == LineBreakToken :
                rendered_out += StringToken("<BR>")
            elif type(token) == HorizontalLineToken :
                rendered_out += StringToken("\n<HR>\n")
            elif type(token) is StringToken :
                if token.s.strip() == "" :
                    rendered_out += token
                elif in_paragraph or inhibit_paragraph :
                    rendered_out += token
                    inhibit_paragraph = False
                else :
                    in_paragraph = True
                    inhibit_paragraph = False
                    rendered_out += StringToken("<P>") + token
            elif type(token) is InhibitParagraphToken :
                inhibit_paragraph = True
            elif type(token) is ParagraphToken :
                if inhibit_paragraph :
                    inhibit_paragraph = False
                elif in_paragraph :
                    rendered_out += StringToken("</P>\n\n")
                    in_paragraph = False
                else :
                    pass #nothing
            else :
                token.fail("Page cannot render token "+repr(token))
        if in_paragraph :
            rendered_out += StringToken("</P>\n\n")
        return rendered_out

def delay_render_paragraphing(tokens) :
    def _handler(env) :
        return render_paragraphing(tokens.eval(env))
    return LambdaToken(_handler)


###
### Handling enumerate and itemize environments
###

@add_token_handler(token_handlers, "item")
def default_item_handler(stream, char_env, token_env, begin_stack) :
    raise stream.failure("Item token found outside itemize or enumerate.")

def begin_listing_environment(stream, char_env, escape_env) :
    def item_handler(stream, char_env, escape_env, begin_stack) :
        if escape_env.bindings.has_key("_in_list") : # are we in a list /right now/?
            args = read_bracket_args(stream, char_env, escape_env, begin_stack)
            return ItemToken(stream, args)
        else : raise stream.failure("Item token found at wrong level of itemize or enumerate.")
    return (char_env, escape_env.extend({"item" : item_handler, "_in_list" : True}))
def end_listing_environment(tag_name, listtagnames) :
    def _end_listing_environment(char_env, token_env, outer_token_env, out) :
        if type(out) is not ListToken :
            raise Exception("Itemize or enumerate has no \\item.")
        next_item = StringToken("")
        in_item = False
        rout = StringToken("<"+tag_name+">")
        for token in out.tokens :
            if not in_item :
                if type(token) is StringToken and token.s.strip() == "" :
                    pass # just ignore leading whitespace
                elif type(token) is not ItemToken :
                    raise Exception("Itemize or enumerate must start with \\item.")
                else :
                    in_item = True
                    if len(listtagnames) == 1 :
                        rout += StringToken("\n<"+listtagnames[0]+">")
                        if token.textlabel is not None :
                            rout += StringToken("<b>")+token.textlabel+StringToken("</b> ")
                    else :
                        ls = token.textlabel
                        if ls is None :
                            ls = StringToken("")
                        rout += StringToken("\n<"+listtagnames[0]+">") + ls + StringToken("</"+listtagnames[0]+"><"+listtagnames[1]+">")
            else :
                if type(token) is ItemToken :
                    rout += delay_render_paragraphing(next_item)
                    if len(listtagnames) == 1 :
                        rout += StringToken("</"+listtagnames[0]+">\n<"+listtagnames[0]+">")
                        if token.textlabel is not None :
                            rout += StringToken("<b>")+token.textlabel+StringToken("</b> ")
                    else :
                        ls = token.textlabel
                        if ls is None :
                            ls = StringToken("")
                        rout += StringToken("</"+listtagnames[1]+">\n<"+listtagnames[0]+">") + ls + StringToken("</"+listtagnames[0]+"><"+listtagnames[1]+">")
                    next_item = StringToken("")
                else :
                    next_item += token
        if in_item :
            if len(listtagnames) == 1 :
                rout += delay_render_paragraphing(next_item) + StringToken("</"+listtagnames[0]+">\n")
            else :
                rout += delay_render_paragraphing(next_item) + StringToken("</"+listtagnames[1]+">\n")
        rout += StringToken("</"+tag_name+">\n")
        return ParagraphToken() + InhibitParagraphToken() + rout
    return _end_listing_environment
environment_handlers["itemize"] = (begin_listing_environment, end_listing_environment("UL", ("LI",)))
environment_handlers["enumerate"] = (begin_listing_environment, end_listing_environment("OL", ("LI",)))
environment_handlers["description"] = (begin_listing_environment, end_listing_environment("DL", ("DT", "DD")))

###
### Tablular environment
###

@add_char_handler(char_handlers, "&")
def default_col_break_handler(stream, char_env, escape_env, begin_stack) :
    raise stream.failure("No column to break.")

# but I might wanna type an ampersand
@add_token_handler(token_handlers, "&")
def escape_amp_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken("&amp;")

def begin_tabular_environment(stream, char_env, escape_env) :
    def col_break_handler(stream, char_env, escape_env, begin_stack) :
        stream.read()
        return ColumnBreakToken()
    formatting = parse_one(stream, char_env, escape_env, [])
    try :
        formatting = formatting.eval({})
    except AttributeError :
        raise stream.failure("Formatting string for tabular must be evaluatable.")
    if type(formatting) is not StringToken :
        raise stream.failure("Formatting string must be a string.")
    return (char_env.extend({"&" : col_break_handler}),
            escape_env.extend({"_table_formatting" : formatting.s}))
def end_tabular_environment(char_env, token_env, outer_token_env, out) :
    formatting = token_env["_table_formatting"]
    columnformats = decode_column_formats(formatting)
    table = []
    rowformats = []
    cellformats = []
    if type(out) is not ListToken :
        table = [[out]]
        rowformats = [dict()]
    else : # basically to handle hlines and make the table variable the contents of the table.
        currrow = dict()
        celltokens = StringToken("")
        rowtokens = []
        cellformat = [[1,1], dict()] # [[rowspan, colspan], style]
        rowofcellformats = []
        for token in out.tokens :
            if type(token) == ColumnBreakToken or type(token) == LineBreakToken :
                rowtokens.append(celltokens)
                celltokens = StringToken("")
                rowofcellformats.append(cellformat)
                for i in range(1,cellformat[0][1]) : # puts in bunk cells when there's a colspan
                    rowtokens.append(StringToken(""))
                    rowofcellformats.append([[1,1],dict()])
                cellformat = [[1,1], dict()]
                if type(token) == LineBreakToken :
                    rowformats.append(currrow)
                    table.append(rowtokens)
                    currrow = dict()
                    rowtokens = []
                    cellformats.append(rowofcellformats)
                    rowofcellformats = []
            elif type(token) == HorizontalLineToken :
                #if not (celltokens == StringToken("") and len(rowtokens) == []) :
                #    raise Exception("In tabular, \\hline must occur at beginning of row.")
                if currrow.has_key("border-top-style") :
                    currrow["border-top-style"] = "double"
                    currrow["border-top-width"] = "3px"
                else :
                    currrow["border-top-style"] = "solid"
            elif type(token) is RowSpanToken :
                cellformat[0][0] = token.rows
            elif type(token) is ColSpanToken :
                cellformat[0][1] = token.cols
                for key,value in token.formatting.iteritems() :
                    cellformat[1][key] = value
            else :
                celltokens += token
        # put in residual formatting, for instance a trailing hline
        if len(rowtokens) == 0 and type(celltokens) == StringToken and celltokens.s.strip() == "" :
            if len(table) == 0 :
                raise Exception("Tabular environment has no rows.")
            for key, value in currrow.iteritems() :
                if key == "border-top-style" :
                    rowformats[-1]["border-bottom-style"] = value
                elif key == "border-top-width" :
                    rowformats[-1]["border-bottom-width"] = value
        else : # otherwise it's actually content.
            if celltokens != StringToken("") :
                rowtokens.append(celltokens)
                rowofcellformats.append(cellformat)
            if len(rowtokens) != 0 :
                for i in range(1,cellformat[0][1]) :
                    rowtokens.append(StringToken(""))
                    rowofcellformats.append([[1,1],dict()])
                rowformats.append(currrow)
                table.append(rowtokens)
                cellformats.append(rowofcellformats)
    rout = StringToken("<TABLE class=\"tabular\" style=\"border-collapse: collapse;\">\n")
    ignore = [[False for c in row] for row in table]
    for r in range(0, len(table)) :
        rout += StringToken("<TR>")
        for c in range(0, len(table[r])) :
            if not ignore[r][c] :
                style = rowformats[r].copy()
                for key,value in columnformats[c].iteritems() :
                    style[key] = value
                for key,value in cellformats[r][c][1].iteritems() :
                    style[key] = value
                t = table[r][c]
                rowspan, colspan = cellformats[r][c][0]
                spanstring = ""
                if rowspan > 1 :
                    for i in range(1,rowspan) :
                        if len(ignore) > r + i and len(ignore[r+i]) > c :
                            ignore[r+i][c] = True
                    for key,value in rowformats[r+rowspan-1].iteritems() : # to get the styles from the last row
                        if key == "border-bottom-style" or key == "border-bottom-width" :
                            style[key] = value
                    spanstring += "ROWSPAN="+str(rowspan) + " "
                    style["vertical-align"] = "middle"
                if colspan > 1 :
                    for i in range(1,colspan) :
                        if len(ignore) > r and len(ignore[r]) > c + i :
                            ignore[r][c+i] = True
                    spanstring += "COLSPAN="+str(colspan) + " "
                s = "; ".join([key+": "+value for key,value in style.iteritems()])
                rout += StringToken("<TD "+spanstring+"style=\""+s+"\">") + table[r][c] + StringToken("</TD>")
        rout += StringToken("</TR>\n")
    rout += StringToken("</TABLE>\n")
    return ParagraphToken() + InhibitParagraphToken() + rout
environment_handlers["tabular"] = (begin_tabular_environment, end_tabular_environment)

class RowSpanToken(SelfEvaluatingToken) :
    def __init__(self, rows, width) :
        self.rows = rows
        self.width = width
class ColSpanToken(SelfEvaluatingToken) :
    def __init__(self, cols, formatting) :
        self.cols = cols
        self.formatting = formatting
@add_token_handler(token_handlers, "multicolumn")
def multicolumn_handler(stream, char_env, token_env, begin_stack) :
    numcols = parse_one(stream, char_env, token_env, begin_stack)
    formatting = parse_one(stream, char_env, token_env, begin_stack)
    try :
        numcols = numcols.eval({})
        formatting = formatting.eval({})
    except AttributeError :
        raise stream.failure("Number of columns and formatting string for multicolumn must be evaluatable.")
    try :
        numcols = int(numcols.s)
    except :
        raise stream.failure("The number of columns for multicolumn must be an integer.")
    if type(formatting) is not StringToken :
        raise stream.failure("Formatting string must be a string for multicolumn.")
    f = decode_column_formats(formatting.s)
    if len(f) != 1 :
        raise stream.failure("Multicolumn must have formatting for exactly one column.")
    return ColSpanToken(numcols, f[0])
@add_token_handler(token_handlers, "multirow")
def multirow_handler(stream, char_env, token_env, begin_stack) :
    numrows = parse_one(stream, char_env, token_env, begin_stack)
    width = parse_one(stream, char_env, token_env, begin_stack)
    try :
        numrows = numrows.eval({})
        width = width.eval({})
    except AttributeError :
        raise stream.failure("Number of rows and width string for multirow must be evaluatable.")
    try :
        numrows = int(numrows.s)
    except :
        raise stream.failure("The number of rows for multirow must be an integer.")
    if type(width) is not StringToken :
        raise stream.failure("Width string must be a string for multirow.")
    return RowSpanToken(numrows, width.s)

def decode_column_formats(formatting) :
    # figure out formatting
    columnformats = []
    currcolumn = dict()
    for c in formatting :
        if c == " " :
            pass
        elif c == "|" :
            if currcolumn.has_key("border-left-style") :
                currcolumn["border-left-style"] = "double"
                currcolumn["border-left-width"] = "3px"
            else :
                currcolumn["border-left-style"] = "solid"
        elif c in "lcr" :
            currcolumn["text-align"] = {"l":"left", "c":"center", "r":"right"}[c]
            columnformats.append(currcolumn)
            currcolumn = dict()
        else :
            raise Exception("Character "+repr(c)+" not a format code for columns in "+repr(formatting)+" of tabular environment")
    if len(columnformats) == 0 :
        raise Exception("Format code "+repr(formatting)+" for columns of tabular environment has no columns.")
    # take residual formatting and apply it to last column
    for key, value in currcolumn.iteritems() :
        if key == "border-left-style" :
            columnformats[-1]["border-right-style"] = value
        elif key == "border-left-width" :
            columnformats[-1]["border-right-width"] = value
    return columnformats

###
### Text justification environments
###

def begin_center_environment(stream, char_env, escape_env) :
    return (char_env, escape_env)
def end_center_environment(char_env, escape_env, outer_token_env, out) :
    return InhibitParagraphToken()+StringToken("<CENTER>") + out + StringToken("</CENTER>\n")
environment_handlers["center"] = (begin_center_environment, end_center_environment)

def begin_quote_environment(stream, char_env, escape_env) :
    return (char_env, escape_env)
def end_quote_environment(char_env, escape_env, outer_token_env, out) :
    return (InhibitParagraphToken()+StringToken("<BLOCKQUOTE>") +
            ParagraphToken() + out + StringToken("</BLOCKQUOTE>\n"))
environment_handlers["quote"] = (begin_quote_environment, end_quote_environment)

def begin_abstract_environment(stream, char_env, escape_env) :
    return (char_env, escape_env)
def end_abstract_environment(char_env, escape_env, outer_token_env, out) :
    return (InhibitParagraphToken()+
            StringToken("<DIV CLASS=\"abstract\"><DIV CLASS=\"abstractcaption\">Abstract</DIV>") +
            ParagraphToken() + out + StringToken("</DIV>\n"))
environment_handlers["abstract"] = (begin_abstract_environment, end_abstract_environment)


add_counter("figure", "page")

def begin_figure_environment(stream, char_env, escape_env) :
    placement = read_bracket_args(stream, char_env, escape_env, [])
    newenv = escape_env.extend({})
    newenv["_figure_placement"] = placement
    return (char_env, newenv)
def end_figure_environment(char_env, escape_env, outer_token_env, out) :
    def _handler(env) :
        get_counter("figure").increment()
        id = generate_id("figure", get_counter("page"), get_counter("figure"))
        set_anchor_reference(outer_token_env, id, StringToken(str(counters_to_string("figure"))))
        p = escape_env["_figure_placement"].eval(env)
        if type(p) is not StringToken :
            p.fail("Figure placement must be a string.")
        o = (ParagraphToken() + InhibitParagraphToken() + get_anchor_by_id(id) + InhibitParagraphToken()
             + StringToken("<div class=\"figure figure_"+p.s+"\">") + out + StringToken("</div>")
             + ParagraphToken())
        return o
    return LambdaToken(_handler)
environment_handlers["figure"] = (begin_figure_environment, end_figure_environment)

@add_token_handler(token_handlers, "caption")
def caption_handler(stream, char_env, escape_env, begin_stack) :
    text = parse_one(stream, char_env, escape_env, begin_stack)
    def _handler(env) :
        teval = text.eval(env)
        return (StringToken("<div class=\"caption\"><b>Figure "+counters_to_string("figure")+".</b> ")+teval
                +StringToken("</div>"))
    return LambdaToken(_handler)

@add_token_handler(token_handlers, "framebox")
@add_token_handler(token_handlers, "fbox")
@make_handler(1)
def framebox_handler(text) :
    return StringToken("<SPAN CLASS=\"framebox\">") + text + StringToken("</SPAN>")

###
### Verbatim text
###

_html_escape_table = {
    "&": "&amp;",
    ">": "&gt;",
    "<": "&lt;",
    }
def html_escape(text):
    return "".join(_html_escape_table.get(c,c) for c in text)


# handles "\verb|oeuoeau|"
@add_token_handler(token_handlers, "verb")
def verb_handler(stream, char_env, escape_env, begin_stack) :
    delim = stream.read()
    out = []
    c = stream.read()
    while c != delim :
        out.append(c)
        c = stream.read()
    return StringToken("<tt>"+html_escape("".join(out))+"</tt>")

#
# Verbatim environment:
#

def verbatim_passthrough_handler(stream, char_env, escape_env, begin_stack) :
    return StringToken(stream.read())

def verbatim_end_handler(stream, char_env, escape_env, begin_stack) :
    end_verbatim_text = "\\end{verbatim}"
    i = 0
    c = stream.peek()
    while c == end_verbatim_text[i] :
        stream.read()
        if c == "" :
            raise stream.failure("End of stream reached before end of verbatim environment.")
        i += 1
        if i == len(end_verbatim_text) :
            return EndEnvToken("verbatim")
        c = stream.peek()
    return StringToken(end_verbatim_text[:i])

def begin_verbatim_environment(stream, char_env, escape_env) :
    new_base_env = DefaultCharacterEnvironment(verbatim_passthrough_handler)
    new_env = CharacterEnvironment({"\\" : verbatim_end_handler}, new_base_env)
    return (new_env, escape_env)
def end_verbatim_environment(char_env, escape_env, outer_token_env, out) :
    if type(out) is not StringToken :
        raise Exception("Something bad happened with the verbatim environment.")
    return StringToken("<pre>"+html_escape(out.s.split("\n", 1)[1])+"</pre>")
environment_handlers["verbatim"] = (begin_verbatim_environment, end_verbatim_environment)

###
### Templates and stylesheets
###

# \setpagetemplate
@add_token_handler(token_handlers, "setpagetemplate")
def set_page_template(stream, char_env, token_env, begin_stack) :
    name = parse_one(stream, char_env, token_env, begin_stack)
    try :
        name = name.eval({})
    except AttributeError :
        raise stream.failure("Name must not be parameterized for set_page_template.")
    if type(name) != StringToken :
        raise stream.failure("Name for \\setpagetemplate must be a string.")
    old = token_env["_global_input_dir"]
    fn = os.path.abspath(os.path.join(token_env["_global_input_dir"], name.s))
    token_env["_global_input_dir"] = os.path.split(fn)[0]
    token_env["_page_template"] = parse_all(fileStream(fn), char_env, token_env, [], execute=False)
    token_env["_global_input_dir"] = old
    return StringToken("")

# \setstylesheet{filename}.  Filename must be unique, otherwise things
# will get overwritten!
@add_token_handler(token_handlers, "setstylesheet")
def set_stylesheet_handler(stream, char_env, token_env, begin_stack) :
    name = parse_one(stream, char_env, token_env, begin_stack)
    try :
        name = name.eval({})
    except AttributeError :
        raise stream.failure("Name must not be parameterized for setstylesheet.")
    if type(name) != StringToken :
        raise stream.failure("Name for \\setstylesheet must be a string.")
    filename = os.path.abspath(os.path.join(token_env["_global_input_dir"], name.s))
    cssdir = os.path.join(token_env["_global_base_out_dir"], "css")
    if not os.path.isdir(cssdir) :
        os.makedirs(cssdir, 0755)
    filestail = os.path.split(filename)[1]
    destname = os.path.join(cssdir, filestail)
    shutil.copy(filename, destname)
    token_env["_page_css"] = destname
    return StringToken("")

# sections

@add_token_handler(token_handlers, "section")
def section_handler(stream, char_env, token_env, begin_stack) :
    text = parse_one(stream, char_env, token_env, begin_stack)
    def _handler(env) :
        get_counter("section").increment()
        id = generate_id("section", get_counter("page"), get_counter("section"))
        set_anchor_reference(token_env, id, text)
        return (ParagraphToken() + InhibitParagraphToken() + get_anchor_by_id(id) + InhibitParagraphToken()
                + StringToken("<H2>"+counters_to_string("section")+". ") + text + StringToken("</H2>")
                + ParagraphToken())
    return LambdaToken(_handler)

@add_token_handler(token_handlers, "subsection")
def subsection_handler(stream, char_env, token_env, begin_stack) :
    text = parse_one(stream, char_env, token_env, begin_stack)
    def _handler(env) :
        get_counter("subsection").increment()
        id = generate_id("subsection", get_counter("page"), get_counter("section"), get_counter("subsection"))
        set_anchor_reference(token_env, id, text)
        return (ParagraphToken() + InhibitParagraphToken() + get_anchor_by_id(id) + InhibitParagraphToken()
                + StringToken("<H3>"+counters_to_string("section", "subsection")+". ") + text + StringToken("</H3>")
                + ParagraphToken())
    return LambdaToken(_handler)

@add_token_handler(token_handlers, "subsubsection")
def subsection_handler(stream, char_env, token_env, begin_stack) :
    text = parse_one(stream, char_env, token_env, begin_stack)
    def _handler(env) :
        get_counter("subsubsection").increment()
        id = generate_id("subsubsection", get_counter("page"), get_counter("section"), get_counter("subsection"), get_counter("subsubsection"))
        set_anchor_reference(token_env, id, text)
        return (ParagraphToken() + InhibitParagraphToken() + get_anchor_by_id(id) + InhibitParagraphToken()
                + StringToken("<H4>"+counters_to_string("section", "subsection", "subsubsection")+". ") + text + StringToken("</H4>")
                + ParagraphToken())
    return LambdaToken(_handler)

###
### Breadcrumbs
###

@add_token_handler(token_handlers, "addbreadcrumb")
def breadcrumb_handler(stream, char_env, token_env, begin_stack) :
    name = read_bracket_args(stream, char_env, token_env, begin_stack)
    label = parse_one(stream, global_char_env, token_env, begin_stack)
    def _handler(env) :
        if "_breadcrumbs" not in token_env["_fluid_let"] :
            token_env["_fluid_let"].append("_breadcrumbs")
            token_env["_breadcrumbs"] = []
        token_env["_breadcrumbs"] = (token_env["_breadcrumbs"]
                                     + [(name if name is None else name.eval(env),label.eval(env))])
        return StringToken("")
    return LambdaToken(_handler)

@add_token_handler(token_handlers, "popbreadcrumb")
def popbreadcrumb_handler(stream, char_env, token_env, begin_stack) :
    def _handler(env) :
        token_env["_breadcrumbs"] = token_env["_breadcrumbs"][0:-1]
        return StringToken("")
    return LambdaToken(_handler)
