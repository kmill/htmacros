# references.py
#
# handles references and counters

from lazytokens import (StringToken, LambdaToken, ListToken, VariableToken, InhibitParagraphToken)
from environments import (add_char_handler, add_token_handler)
from parser import (parse_one, read_bracket_args, global_char_env)
import pickle
import os.path
import urllib

# any module with macros needs to have these variables
char_handlers = dict()
token_handlers = dict()
environment_handlers = dict()

_counters = dict()

class Counter(object) :
    def __init__(self, name) :
        self.i = 0
        self.subcounters = []
        self.name = name
    def increment(self) :
        self.i += 1
        for c in self.subcounters :
            c.reset()
    def reset(self) :
        self.i = 0
        for c in self.subcounters :
            c.reset()
    def add_subcounter(self, c) :
        self.subcounters.append(c)
    def __str__(self) :
        return str(self.i)
    def __repr__(self) :
        return "<Counter "+repr(self.name)+" i="+repr(self.i)+">"

def add_counter(name, subcounter_of=None) :
    _counters[name] = Counter(name)
    if subcounter_of is not None :
        get_counter(subcounter_of).add_subcounter(get_counter(name))

def get_counter(name) :
    if _counters.has_key(name) :
        return _counters[name]
    else :
        raise Exception("No such counter "+name)

def counters_to_string(*counters, **kwargs) :
    sep = kwargs.get("sep", ".")
    return sep.join([str(get_counter(name).i) for name in counters])

def generate_id(*items) :
    return "_".join([str(i) for i in items])

add_counter("page")
add_counter("section", "page")
add_counter("subsection", "section")
add_counter("subsubsection", "subsection")


###
### Links
###

class LinkReference(object) :
    def __init__(self, id, autoname, labelname, dir, filename, anchor) :
        self.id = id
        self.autoname = autoname
        self.labelname = labelname
        self.dir = dir
        self.filename = filename
        self.anchor = anchor
    def relative_link(self, fromdir, insides) :
        path = os.path.join(os.path.relpath(self.dir, fromdir), self.filename)
        return StringToken("<A HREF=\"" + path + ("" if self.anchor is None
                                                  else ("#"+urllib.quote_plus(self.anchor)))
                           +"\">") + insides + StringToken("</A>")
    def make_anchor(self) :
        return StringToken("<A NAME=\"" + urllib.quote_plus(self.anchor) + "\"></A>")
    def get_name(self) :
        if self.anchor is None :
            return self.labelname
        else :
            return self.labelname + "#" + self.anchor
    def path(self) : # the output file which contains the reference
        return os.path.join(self.dir, self.filename)
    def __eq__(self, other) :
        return type(other) == LinkReference and (self.id, self.autoname, self.labelname, self.dir, self.filename, self.anchor) == (other.id, other.autoname, other.labelname, other.dir, other.filename, other.anchor)
    def __repr__(self) :
        return "<LinkReference id=%r autoname=%r labelname=%r dir=%r filename=%r anchor=%r>" % (self.id, self.autoname, self.labelname, self.dir, self.filename, self.anchor)

class PendingPageReference(object) :
    def __init__(self, id, filename, dir) :
        self.id = id
        self.filename = filename
        self.dir = dir
    def make_link_reference(self, labelname) :
        return LinkReference(self.id, labelname, labelname, self.dir, self.filename, None)

class PendingAnchorReference(object) :
    def __init__(self, id, autoname, pagereference) :
        self.id = id
        self.autoname = autoname
        self.pagereference = pagereference
    def make_link_reference(self, anchor) :
        return LinkReference(self.id, self.autoname, self.pagereference.labelname, self.pagereference.dir, self.pagereference.filename, anchor)

_last_object_for_label = None
def set_page_reference(token_env, id, name) :
    global _last_object_for_label
    _last_object_for_label = PendingPageReference(id, name, token_env["_curr_out_dir"])
def set_anchor_reference(token_env, id, autoname) :
    global _last_object_for_label
    if token_env.has_key("_curr_page_reference") :
        _last_object_for_label = PendingAnchorReference(id, autoname, token_env["_curr_page_reference"])
    else :
        raise Exception("No page reference given, so can't create anchor for id "+repr(id))

def get_anchor_by_id(id) :
    if _id_to_reference_name.has_key(id) :
        return _references[_id_to_reference_name[id]].make_anchor()
    elif _old_id_to_reference_name.has_key(id) :
        return _old_references[_old_id_to_reference_name[id]].make_anchor()
    else :
        #print "No such reference with id "+repr(id) # this happens when the object never gets a label
        return StringToken("")

def get_autoname_by_ref_name(ref) :
    if _references.has_key(ref) :
        return _references[ref].autoname
    elif _old_references.has_key(ref) :
        return _old_references[ref].autoname
    else :
        return StringToken("<B>(?? reference ??)</B>")

_labels_changed = False
_references = dict()
_id_to_reference_name = dict()

_old_references = dict()
_old_id_to_reference_name = dict()

def serialize_link_references(filename) :
    global _labels_changed
    if not ((_references == _old_references) and (_id_to_reference_name == _old_id_to_reference_name)) :
        _labels_changed = True
    file = open(filename + ".ref", "w")
    pickle.dump([_references, _id_to_reference_name], file)
    file.close()

def unserialize_link_references(filename) :
    global _old_references, _old_id_to_reference_name
    if os.path.isfile(filename + ".ref") :
        file = open(filename + ".ref", "r")
        rs = pickle.load(file)
        _old_references = rs[0]
        _old_id_to_reference_name = rs[1]
        file.close()

@add_token_handler(token_handlers, "label")
def label_handler(stream, char_env, token_env, begin_stack) :
    poss_failure = stream.failure()
    name = parse_one(stream, global_char_env, token_env, begin_stack)
    def _handler(env) :
        global _last_object_for_label
        try :
            n = name.eval(env)
        except AttributeError :
            raise poss_failure.with_message("Label name must be able to be evaluated.")
        if type(n) is not StringToken :
            raise poss_failure.with_message("Label must be a string.")
        labelname = n.s
        if _last_object_for_label is None :
            raise poss_failure.with_message("Label "+repr(labelname)+" given for no object.")

        lr = _last_object_for_label.make_link_reference(labelname)
        if type(_last_object_for_label) is PendingPageReference :
            token_env["_curr_page_reference"] = lr
            token_env["_curr_page_label"] = labelname
        _last_object_for_label = False
        _references[lr.get_name()] = lr
        _id_to_reference_name[lr.id] = lr.get_name()
        return InhibitParagraphToken()
    return LambdaToken(_handler)

@add_token_handler(token_handlers, "ref")
def ref_handler(stream, char_env, token_env, begin_stack) :
    poss_err = stream.failure()
    barg = read_bracket_args(stream, char_env, token_env, begin_stack)
    labelname = parse_one(stream, global_char_env, token_env, begin_stack)
    return make_reference(token_env, labelname, barg)


def make_reference(token_env, labelname, barg) :
    def _handler(env) :
        try :
            ln = labelname.eval(env)
        except AttributeError :
            raise Exception("Label must be evaluatable for ref.")
        if type(ln) != StringToken :
            raise Exception("Label for ref must be string.")
        ln = ln.s
        if ln.startswith("#") :
            ln = token_env["_curr_page_label"]+ln
        if not _references.has_key(ln) :
            if not _old_references.has_key(ln) :
                print "No such reference "+repr(ln)+"."
                return StringToken("<B>(?? reference ??)</B>")
            else :
                ref = _old_references[ln]
        else :
            ref = _references[ln]
        if barg is not None :
            text = barg
        else :
            text = ref.autoname
        a = ref.relative_link(token_env["_curr_out_dir"], text)
        return a
    return LambdaToken(_handler)

# for external links
@add_token_handler(token_handlers, "link")
def link_handler(stream, char_env, token_env, begin_stack) :
    poss_err = stream.failure()
    barg = read_bracket_args(stream, char_env, token_env, begin_stack)
    linkurl = parse_one(stream, global_char_env, token_env, begin_stack)
    if barg is None :
        barg = linkurl
    return StringToken("<A HREF=\"") + linkurl + StringToken("\">") + barg + StringToken("</A>")
