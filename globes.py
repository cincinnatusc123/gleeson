import os
import re

#names should match up with self.name of plates.py

ROOT_DIR = "/home/Gleeson/database"
OUT_DIR = "%s/output" % ROOT_DIR

#Jobs output from triton have their last line as 'Nodes:    ttc....'
#Once we reach there stop iteratin through the file
def tritonStop( splt ) :
    return "Nodes" in splt[0]

#TODO
#very weird behavior if give digits default of []
#it somehow uses the last returned value of digits as the new starting point
#instead
def toBaseN( num, n, digits ) :
    d = num / n
    remainder = num % n
    digits.append( remainder )

    if d < n :
        digits.append( d )
        digits.reverse()
        return int(''.join(map(str,digits)))
    else :
        return toBaseN( d, n, digits )


def dontStop( splt ) : return False
def assertSane( splt ) : return (True,"good to go")
#turn a filename into a line iterator, returning line splits
#headerSanityCheck checks that the specified line (header_line_num)
#does indeed meet the expectations of what should be in this file
#burn specifies the number of lines to discard before yielding 
#stopper is a function that decides when to raise a StopIteratiion
def splitIterator( fh_or_name, sep='\t', burn=0, \
                   header_line_num = 0, \
                   headerSanityCheck = assertSane, \
                   skipLine = dontStop, \
                   stopIter = dontStop ) :
    if type(fh_or_name) == file :
        handle = fh_or_name
    else :
        handle = open(fh_or_name)
    count = 0
    while count < burn :
        line = handle.readline()
        if count == header_line_num :
            splt = line.strip('\n').split(sep)
            (ok,message) = headerSanityCheck( splt )
            if not ok :
                print message
                raise StopIteration
        count += 1
    
    for line in handle :
        splt = line.strip('\n').split(sep)
        if stopIter( splt ) :
            handle.close()
            raise StopIteration
        elif skipLine( splt ) : continue
        else : 
            yield splt

    handle.close()

def debug( s, indent=0 ) :
    if DEBUG : print "%s%s" % (" "*4*indent, s)

#turns a chromosome string into another string that will sort correctly
#ie. 1,2,3,...,10,11,12,...,21,22,X,Y instead of
#    1,10,11,12,...22,31,32
def chromNum( chrom ) :
    if type(chrom) == int or type(chrom) == long : return chrom

    chrom = chrom.strip("chr")
    if chrom == 'X' : return 23
    elif chrom == 'Y' : return 24
    else :
        try : return int(chrom)
        except ValueError :
            print "chromNum can't cast %s to int, maan" % chrom
            return 25

def compareHelper( a,b ) :
    if a == '*' or b == '*' : return 0

    if a < b : return -1
    elif a == b : return 0
    else : return 1

base_order = ['a','c','g','t','n']
def compareVariants( chr1,pos1,ref1,mut1, \
                     chr2,pos2,ref2,mut2 ) :
    chr1,chr2 = chromNum(chr1), chromNum(chr2)
    pos1,pos2 = int(pos1),int(pos2)
    ref1,ref2 = ref1.lower(),ref2.lower()
    mut1,mut2 = mut1.lower(),mut2.lower()

    levels = ((chr1,chr2),(pos1,pos2),(ref1,ref2),(mut1,mut2))
    for (a,b) in levels :
        r = compareHelper(a,b)
        if not r == 0 : return r
    return r

def comparePositions( chr1, pos1, chr2, pos2 ) :
    pos1,pos2 = int(pos1),int(pos2)
    diff = chromNum(chr1) - chromNum(chr2)
    if diff < 0 :
        return -1
    elif diff == 0 :
        if pos1 < pos2 : return -1
        elif pos1 == pos2 : return 0
        else : return 1
    else :
        return 1

def areOverlapping( s1,e1,s2,e2 ) :
    assert s1 <= e1 and s2 <= e2
    return s1 <= e2 and e1 >= s2

def sortKeysByValues( d ) :
    return sorted( d, key= lambda x : d[x] )

def printColumnWarning( file, indexOf ) :
    print "ATTENTION! The columns of: '%s' better match up with:\n" % file
    skeys = sortKeysByValues( indexOf )
    for key in skeys :
        print "    %s : %d" % (key, indexOf[key])


re_dbSNP_digits = re.compile(r'rs(\d+)[A:TCGEn]')
def justDigitsFromDBSNP( dbSNP ) :
    m = re_dbSNP_digits.match( dbSNP )
    if m : return m.group(1)
    else : raise Exception("getDBSNPDigits: Cannot parse dbSNP")


#if a string has a bunch of contiguous integers, return it
re_nondigit = re.compile(r'[^\d]*')
def stripNonNumbers( string ) :
    return int(re_nondigit.sub( '',string ))

if __name__ == '__main__' :
   #s1,e1 = 5,10
   #s2,e2 = 4,8
#
   #print areOverlapping(s1,e1,s2,e2)

    #print compareVariants( 1,23,'a','t',1,\
                           #1,23,'a','t',1 )

    print toBaseN( 16, 5 )
