#!/usr/bin/env python
import parser
import streams
import references
import os
import sys

def runhm(inpfile, outdir) :
    parser.set_input_dir(os.path.split(inpfile)[0])
    parser.set_global_output_dir(outdir)
    references.unserialize_link_references(inpfile)
    parser.global_parse(streams.fileStream(inpfile))
    references.serialize_link_references(inpfile)

#    print "\nFinal references:"
#    print "_references",references._references,"\n"
#    print "_id_to_reference_name",references._id_to_reference_name

    if references._labels_changed :
        print "\n***Run again to get labels right.***\n"
    else :
        print "\n***Done***\n"

if __name__=="__main__" :
    if len(sys.argv) != 3 :
        print "Usage: %s inpfile outdir" % sys.argv[0]
    else :
        runhm(sys.argv[1], sys.argv[2])
